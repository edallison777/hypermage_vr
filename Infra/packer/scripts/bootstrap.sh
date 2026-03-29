#!/usr/bin/env bash
# bootstrap.sh — Installs UE5.3, Android SDK, and GameLift SDK on Amazon Linux 2023
# Executed by Packer on the build instance. Takes 4-8 hours (UE5.3 source compile).
set -euo pipefail

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ── 1. System dependencies ────────────────────────────────────────────────────
log "Installing system dependencies..."
sudo dnf update -y
sudo dnf groupinstall "Development Tools" -y
sudo dnf install -y \
  git \
  cmake \
  python3 \
  python3-pip \
  clang \
  wget \
  unzip \
  jq \
  aws-cli \
  dotnet-sdk-8.0 \
  perl \
  libuuid-devel \
  openssl-devel \
  libcurl-devel \
  zlib-devel \
  xz \
  ncurses \
  amazon-cloudwatch-agent

# clang alias expected by UE5.3 build scripts
sudo ln -sf /usr/bin/clang /usr/local/bin/clang-13 2>/dev/null || true
sudo ln -sf /usr/bin/clang++ /usr/local/bin/clang++-13 2>/dev/null || true

log "System dependencies installed."

# ── 2. Unreal Engine 5.3 from source ─────────────────────────────────────────
# Requires GitHub account linked to Epic Games at https://github.com/EpicGames/UnrealEngine
# The instance must have an IAM role or the repo must be public — use a GitHub PAT via
# the UE5_GITHUB_TOKEN env var if needed, or pre-authorise the key pair.
log "Cloning Unreal Engine 5.3 (this takes ~30 minutes)..."
sudo mkdir -p /opt/UnrealEngine
sudo chown ec2-user:ec2-user /opt/UnrealEngine

# Use a credential helper so the PAT never appears in the remote URL, process
# listings, or .git/config.  The helper is unset immediately after the clone.
git config --global credential.helper \
  '!f() { echo "username=oauth2"; echo "password='"${UE5_GITHUB_TOKEN}"'"; }; f'

git clone \
  --depth 1 \
  --branch "5.3" \
  "https://github.com/EpicGames/UnrealEngine.git" \
  /opt/UnrealEngine

# Remove the credential helper — token must not persist in git config
git config --global --unset credential.helper

log "Running Setup.sh (~15 minutes)..."
cd /opt/UnrealEngine
./Setup.sh

log "Generating project files..."
./GenerateProjectFiles.sh

log "Compiling Unreal Engine (4-8 hours)..."
make -j$(nproc)

log "Unreal Engine 5.3 compiled successfully."

# ── 3. Android SDK & NDK ──────────────────────────────────────────────────────
log "Installing Android SDK..."
sudo mkdir -p /opt/android-sdk/cmdline-tools
cd /tmp
sudo wget -q \
  "https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip" \
  -O cmdlinetools.zip
sudo unzip -q cmdlinetools.zip -d /opt/android-sdk/cmdline-tools
sudo mv /opt/android-sdk/cmdline-tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest
sudo rm cmdlinetools.zip

export ANDROID_HOME=/opt/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

log "Accepting Android SDK licences..."
yes | sudo $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager \
  --sdk_root=$ANDROID_HOME \
  --licenses >/dev/null 2>&1 || true

log "Installing Android SDK packages (platform-tools, android-33, build-tools 33.0.2, NDK 25.2)..."
sudo $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager \
  --sdk_root=$ANDROID_HOME \
  "platform-tools" \
  "platforms;android-33" \
  "build-tools;33.0.2" \
  "ndk;25.2.9519653"

sudo chown -R ec2-user:ec2-user /opt/android-sdk
log "Android SDK installed."

# ── 4. GameLift SDK ───────────────────────────────────────────────────────────
log "Installing GameLift Server SDK (06_03_2024)..."
cd /opt
sudo wget -q \
  "https://gamelift-release.s3-us-west-2.amazonaws.com/GameLift_06_03_2024.zip" \
  -O GameLift_06_03_2024.zip
sudo unzip -q GameLift_06_03_2024.zip -d GameLiftSDK
sudo rm GameLift_06_03_2024.zip
sudo chown -R ec2-user:ec2-user /opt/GameLiftSDK
log "GameLift SDK installed."

# ── 5. CloudWatch agent config ────────────────────────────────────────────────
log "Configuring CloudWatch agent..."
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json >/dev/null <<'EOF'
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/messages",
            "log_group_name": "/aws/ec2/unreal-build/system",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/build/workspace/build.log",
            "log_group_name": "/aws/ec2/unreal-build/builds",
            "log_stream_name": "{instance_id}-build"
          }
        ]
      }
    }
  }
}
EOF
sudo systemctl enable amazon-cloudwatch-agent || true

# ── 6. Environment variables ──────────────────────────────────────────────────
log "Setting environment variables..."
sudo tee -a /etc/environment >/dev/null <<'EOF'

# HyperMage VR build environment
UE5_ROOT=/opt/UnrealEngine
ANDROID_HOME=/opt/android-sdk
GAMELIFT_SDK_ROOT=/opt/GameLiftSDK
PATH=$PATH:/opt/UnrealEngine/Engine/Binaries/Linux:/opt/android-sdk/platform-tools:/opt/android-sdk/cmdline-tools/latest/bin
EOF

# Also write a profile.d script so sourcing /etc/profile.d picks it up
sudo tee /etc/profile.d/hypermage-build.sh >/dev/null <<'EOF'
export UE5_ROOT=/opt/UnrealEngine
export ANDROID_HOME=/opt/android-sdk
export GAMELIFT_SDK_ROOT=/opt/GameLiftSDK
export PATH=$PATH:$UE5_ROOT/Engine/Binaries/Linux:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin
EOF

# ── 7. Build workspace ────────────────────────────────────────────────────────
sudo mkdir -p /build/workspace /build/output
sudo chown -R ec2-user:ec2-user /build

# ── 8. Final credential scrub ─────────────────────────────────────────────────
# Ensure no PAT survives in git remote URLs inside the cloned repo or global config.
git -C /opt/UnrealEngine remote set-url origin "https://github.com/EpicGames/UnrealEngine.git"
git config --global --unset-all credential.helper 2>/dev/null || true
rm -f ~/.git-credentials /root/.git-credentials

log "Bootstrap complete. Build environment ready."
