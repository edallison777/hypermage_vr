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
  region        = var.aws_region
  instance_type = var.instance_type
  source_ami    = data.amazon-ami.al2023.id
  ssh_username  = "ec2-user"

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

  # Disable source/destination checks (not needed but harmless)
  # Use spot instances to cut build cost ~70%
  spot_instance_types = [var.instance_type]
  spot_price          = "auto"

  # Build takes up to 8 hours for UE5.3 from source
  ssh_timeout         = "10m"
  ssh_handshake_attempts = 60
}

# ── Build ─────────────────────────────────────────────────────────────────────

build {
  sources = ["source.amazon-ebs.ue5_build"]

  # Step 1–9: Install all dependencies and UE5.3 from source
  provisioner "shell" {
    script            = "${path.root}/scripts/bootstrap.sh"
    timeout           = "480m" # 8 hours — UE5.3 compilation from source
    execute_command   = "chmod +x {{ .Path }}; sudo -H -u ec2-user bash '{{ .Path }}'"
    environment_vars  = ["UE5_GITHUB_TOKEN=${var.ue5_github_token}"]
  }

  # Step 10: Verify build environment
  provisioner "shell" {
    inline = [
      "echo '=== Verifying build environment ==='",
      "source /etc/environment || true",
      "export UE5_ROOT=/opt/UnrealEngine",
      "$UE5_ROOT/Engine/Binaries/Linux/UnrealEditor --version || echo 'WARNING: UnrealEditor binary check skipped (headless)'",
      "/opt/android-sdk/platform-tools/adb --version",
      "ls /opt/GameLiftSDK/",
      "echo '=== Build environment OK ==='",
    ]
    timeout = "5m"
  }

  # Step 11: Cleanup before snapshot
  provisioner "shell" {
    inline = [
      "sudo dnf clean all",
      "sudo rm -rf /tmp/* /var/tmp/*",
      "history -c",
      "rm -f ~/.bash_history",
      "sudo rm -f /root/.bash_history",
      "sudo truncate -s 0 /var/log/cloud-init-output.log || true",
    ]
    timeout = "10m"
  }

  # Write AMI manifest for the calling script to parse
  post-processor "manifest" {
    output     = "packer-manifest.json"
    strip_path = true
  }
}
