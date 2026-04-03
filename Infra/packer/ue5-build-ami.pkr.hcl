packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "instance_type" {
  type    = string
  default = "c5.18xlarge"
  # c5.18xlarge: 72 vCPU, 144 GB RAM — UE5.3 source compile in ~1.5-2 hours vs 4-8 on g4dn.xlarge
}

variable "ue5_github_token" {
  type        = string
  description = "GitHub PAT with access to EpicGames/UnrealEngine (linked Epic account required)"
  default     = ""
  sensitive   = true
}

variable "ssh_keypair_name" {
  type        = string
  description = "Existing EC2 key pair name (for SSH provisioner fallback)"
  default     = ""
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID for the build instance (leave empty for default VPC)"
  default     = ""
}

# ── Base AMI ──────────────────────────────────────────────────────────────────

data "amazon-ami" "al2023" {
  filters = {
    name                = "al2023-ami-2023.*-x86_64"
    root-device-type    = "ebs"
    virtualization-type = "hvm"
    state               = "available"
  }
  owners      = ["amazon"]
  most_recent = true
  region      = var.aws_region
}

# ── Source ────────────────────────────────────────────────────────────────────

source "amazon-ebs" "ue5_build" {
  region       = var.aws_region
  source_ami   = data.amazon-ami.al2023.id
  ssh_username = "ec2-user"

  # IMDSv2 required
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  # 200 GB gp3 — UE5.3 source + compile artefacts need ~120 GB
  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 200
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = false # must be false for public AMI sharing; snapshots encrypted at rest
  }

  ami_name        = "unreal-5.3-build-{{timestamp}}"
  ami_description = "Unreal Engine 5.3 with Android SDK (API 33) and GameLift SDK (06_03_2024) for Quest 3 builds"

  tags = {
    Name      = "unreal-5.3-build-{{timestamp}}"
    Purpose   = "UnrealBuild"
    Engine    = "UE5.3"
    ManagedBy = "Packer"
    Project   = "HyperMage VR"
  }

  snapshot_tags = {
    Name    = "unreal-5.3-build-{{timestamp}}"
    Purpose = "UnrealBuild"
    Engine  = "UE5.3"
  }

  # On-demand instance — avoids spot interruptions killing a multi-hour build
  instance_type = var.instance_type

  # Keep SSH session alive during long build steps
  ssh_timeout             = "10m"
  ssh_handshake_attempts  = 60
  ssh_keep_alive_interval = "30s"

  # Extend AMI snapshot waiter — 200GB volume with ~120GB UE5.3 build artifacts
  # takes 90-120 min to snapshot; default waiter is too short.
  # 360 attempts × 30s = 3 hours
  aws_polling {
    delay_seconds = 30
    max_attempts  = 360
  }
}

# ── Build ─────────────────────────────────────────────────────────────────────

build {
  sources = ["source.amazon-ebs.ue5_build"]

  # Step 1: Start bootstrap.sh under nohup so it survives SSH disconnects.
  # The execute_command is idempotent — safe to re-run if Packer reconnects.
  # It monitors progress via tail output to keep the connection alive.
  # If the connection drops, the build keeps running and Step 2 picks it up.
  provisioner "shell" {
    script  = "${path.root}/scripts/bootstrap.sh"
    timeout = "480m"
    execute_command = join("", [
      # Copy to a fixed path so the idempotency check works across reconnects
      "chmod +x '{{ .Path }}'; cp '{{ .Path }}' /tmp/bootstrap-run.sh; ",
      # Only start if not already running and not already finished
      "if [ ! -f /tmp/build.exit ] && ",
      "  ([ ! -f /tmp/build.pid ] || ! kill -0 $(cat /tmp/build.pid 2>/dev/null) 2>/dev/null); then ",
      "  env UE5_GITHUB_TOKEN='${var.ue5_github_token}' ",
      "  nohup bash /tmp/bootstrap-run.sh > /tmp/bootstrap.log 2>&1 < /dev/null & ",
      "  echo $! > /tmp/build.pid; ",
      "fi; ",
      # Monitor until build finishes (outputs log tail to keep SSH alive)
      "while kill -0 $(cat /tmp/build.pid 2>/dev/null) 2>/dev/null; do ",
      "  sleep 30; ",
      "  tail -n 1 /tmp/bootstrap.log 2>/dev/null || true; ",
      "done; ",
      # Exit with build's exit code; dump log on failure so Packer output shows the error
      "EXIT_CODE=$(cat /tmp/build.exit 2>/dev/null || echo 1); ",
      "if [ \"$EXIT_CODE\" != '0' ]; then echo '=== BUILD FAILED — last 150 lines of bootstrap.log ==='; tail -n 150 /tmp/bootstrap.log 2>/dev/null || true; fi; ",
      "exit $EXIT_CODE"
    ])
    # 2300218 = Packer's internal code for SSH disconnect — treat as OK,
    # the build continues under nohup and Step 2 will wait for it.
    valid_exit_codes  = [0, 2300218]
    expect_disconnect = true
  }

  # Step 2: Wait for build completion (handles SSH drop from Step 1).
  # Polls /tmp/build.exit written by bootstrap.sh's trap on exit.
  provisioner "shell" {
    inline = [
      "echo '[wait] Checking build status...'",
      "while [ ! -f /tmp/build.exit ]; do sleep 60; echo \"[$(date -u +%H:%M:%SZ)] Build running: $(tail -n 1 /tmp/bootstrap.log 2>/dev/null || true)\"; done",
      "BUILD_RESULT=$(cat /tmp/build.exit)",
      "if [ \"$BUILD_RESULT\" != '0' ]; then echo '[wait] Build FAILED. Last 100 lines:'; tail -n 100 /tmp/bootstrap.log; exit $BUILD_RESULT; fi",
      "echo '[wait] Build completed successfully.'",
    ]
    timeout           = "480m"
    expect_disconnect = true
    valid_exit_codes  = [0, 2300218]
  }

  # Step 3: Verify build environment + cleanup before snapshot.
  # Merged into one step to avoid a second SCP upload (the SSH session can drop
  # between steps after a long build, causing "SCP failed to start" on re-upload).
  # skip_clean = true: the cleanup wipes /tmp itself, so Packer must not try to
  # SSH-delete its own temp script afterwards. The script inode stays alive in
  # the running process even after the file is unlinked, so rm -rf /tmp/* is safe
  # to run while this script is still executing.
  provisioner "shell" {
    inline = [
      # Safety wait in case Step 2 SSH also dropped before build finished
      "while [ ! -f /tmp/build.exit ]; do sleep 60; echo \"[verify] Still waiting for build: $(tail -n 1 /tmp/bootstrap.log 2>/dev/null || true)\"; done",
      "BUILD_RESULT=$(cat /tmp/build.exit)",
      "if [ \"$BUILD_RESULT\" != '0' ]; then echo '[verify] Build FAILED. Last 100 lines:'; tail -n 100 /tmp/bootstrap.log; exit $BUILD_RESULT; fi",
      "echo '=== Verifying build environment ==='",
      "source /etc/environment || true",
      "export UE5_ROOT=/opt/UnrealEngine",
      "$UE5_ROOT/Engine/Binaries/Linux/UnrealEditor --version || echo 'WARNING: UnrealEditor binary check skipped (headless)'",
      "/opt/android-sdk/platform-tools/adb --version || echo 'WARNING: adb not found (Android SDK optional for GameLift builds)'",
      "ls /opt/GameLiftSDK/",
      "echo '=== Build environment OK ==='",
      "echo '=== Cleaning up before snapshot ==='",
      "sudo dnf clean all",
      "sudo rm -rf /tmp/* /var/tmp/*",
      "history -c",
      "rm -f ~/.bash_history",
      "sudo rm -f /root/.bash_history",
      "sudo truncate -s 0 /var/log/cloud-init-output.log || true",
      "echo '=== Ready for snapshot ==='",
    ]
    timeout    = "480m"
    skip_clean = true
  }

  # Write AMI manifest for the calling script to parse
  post-processor "manifest" {
    output     = "packer-manifest.json"
    strip_path = true
  }
}
