# Unreal Engine 5.3 Build AMI Setup Guide

This guide walks through creating a custom AMI with Unreal Engine 5.3, Android SDK, and GameLift SDK for cloud-based builds.

## Prerequisites

- AWS account with EC2 permissions
- AWS CLI configured
- Basic Linux administration knowledge

## Step 1: Launch Base Instance

Launch an EC2 instance with sufficient resources:

```bash
aws ec2 run-instances \
  --image-id ami-0d940f23d527c3ab1 \
  --instance-type g4dn.xlarge \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxx \
  --subnet-id subnet-xxxxx \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":200,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=UE5-Build-Setup}]'
```

**Recommended Base AMIs:**
- Amazon Linux 2023: `ami-0d940f23d527c3ab1` (eu-west-1)
- Ubuntu 22.04 LTS: `ami-0905a3c97561e0b69` (eu-west-1)

## Step 2: Connect to Instance

```bash
ssh -i your-key-pair.pem ec2-user@<instance-public-ip>
```

## Step 3: Install System Dependencies

### For Amazon Linux 2023:

```bash
sudo dnf update -y
sudo dnf groupinstall "Development Tools" -y
sudo dnf install -y \
  git \
  cmake \
  python3 \
  python3-pip \
  clang \
  mono-complete \
  dotnet-sdk-8.0 \
  wget \
  unzip \
  jq \
  aws-cli
```

### For Ubuntu 22.04:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  build-essential \
  git \
  cmake \
  python3 \
  python3-pip \
  clang \
  mono-complete \
  dotnet-sdk-8.0 \
  wget \
  unzip \
  jq \
  awscli
```

## Step 4: Install Unreal Engine 5.3

### Option A: Build from Source (Recommended)

```bash
# Clone Unreal Engine repository (requires GitHub account linked to Epic Games)
cd /opt
sudo git clone -b 5.3 https://github.com/EpicGames/UnrealEngine.git
cd UnrealEngine

# Setup and build
sudo ./Setup.sh
sudo ./GenerateProjectFiles.sh
sudo make

# Set permissions
sudo chown -R ec2-user:ec2-user /opt/UnrealEngine
```

### Option B: Install from Epic Games Launcher (Alternative)

```bash
# Download Epic Games Launcher for Linux
# Note: This requires manual steps and may not be suitable for automated AMI creation
# See: https://www.unrealengine.com/en-US/linux
```

## Step 5: Install Android SDK and NDK

```bash
# Create Android SDK directory
sudo mkdir -p /opt/android-sdk
cd /opt/android-sdk

# Download Android command-line tools
sudo wget https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip
sudo unzip commandlinetools-linux-9477386_latest.zip
sudo rm commandlinetools-linux-9477386_latest.zip

# Set up SDK manager
export ANDROID_HOME=/opt/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/bin

# Accept licenses and install required packages
yes | sudo $ANDROID_HOME/cmdline-tools/bin/sdkmanager --sdk_root=$ANDROID_HOME --licenses
sudo $ANDROID_HOME/cmdline-tools/bin/sdkmanager --sdk_root=$ANDROID_HOME \
  "platform-tools" \
  "platforms;android-33" \
  "build-tools;33.0.2" \
  "ndk;25.2.9519653"

# Set permissions
sudo chown -R ec2-user:ec2-user /opt/android-sdk
```

## Step 6: Install GameLift SDK

```bash
# Download GameLift SDK
cd /opt
sudo wget https://gamelift-release.s3-us-west-2.amazonaws.com/GameLift_06_03_2024.zip
sudo unzip GameLift_06_03_2024.zip -d GameLiftSDK
sudo rm GameLift_06_03_2024.zip

# Set permissions
sudo chown -R ec2-user:ec2-user /opt/GameLiftSDK
```

## Step 7: Install CloudWatch Agent

```bash
# Download and install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U ./amazon-cloudwatch-agent.rpm
rm amazon-cloudwatch-agent.rpm
```

## Step 8: Configure Environment Variables

```bash
# Add to /etc/environment
sudo tee -a /etc/environment > /dev/null <<EOF
UE5_ROOT=/opt/UnrealEngine
ANDROID_HOME=/opt/android-sdk
GAMELIFT_SDK_ROOT=/opt/GameLiftSDK
PATH=$PATH:/opt/UnrealEngine/Engine/Binaries/Linux:/opt/android-sdk/platform-tools
EOF

# Source environment
source /etc/environment
```

## Step 9: Create Build Workspace

```bash
# Create workspace directory
sudo mkdir -p /build/workspace
sudo chown -R ec2-user:ec2-user /build
```

## Step 10: Test Build Environment

```bash
# Verify Unreal Engine
/opt/UnrealEngine/Engine/Binaries/Linux/UnrealEditor --version

# Verify Android SDK
$ANDROID_HOME/platform-tools/adb --version

# Verify GameLift SDK
ls -la /opt/GameLiftSDK
```

## Step 11: Clean Up

```bash
# Remove temporary files
sudo dnf clean all  # Amazon Linux
# or
sudo apt clean     # Ubuntu

# Clear bash history
history -c
rm ~/.bash_history
```

## Step 12: Create AMI

From your local machine:

```bash
# Get instance ID
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=UE5-Build-Setup" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

# Stop instance
aws ec2 stop-instances --instance-ids $INSTANCE_ID
aws ec2 wait instance-stopped --instance-ids $INSTANCE_ID

# Create AMI
AMI_ID=$(aws ec2 create-image \
  --instance-id $INSTANCE_ID \
  --name "unreal-5.3-build-$(date +%Y%m%d-%H%M%S)" \
  --description "Unreal Engine 5.3 with Android SDK and GameLift SDK for Quest 3 builds" \
  --tag-specifications 'ResourceType=image,Tags=[{Key=Purpose,Value=UnrealBuild},{Key=Engine,Value=UE5.3}]' \
  --output text)

echo "AMI ID: $AMI_ID"

# Wait for AMI to be available
aws ec2 wait image-available --image-ids $AMI_ID

# Terminate setup instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
```

## Step 13: Update Terraform Configuration

Update your Terraform configuration with the new AMI ID:

```hcl
module "unreal_build" {
  source = "./modules/unreal-build"
  
  ami_id = "ami-xxxxx"  # Your new AMI ID
  # ... other configuration
}
```

## Verification

Test the AMI by launching an instance and running a build:

```bash
# Launch test instance
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type g4dn.xlarge \
  --key-name your-key-pair

# SSH to instance and test
ssh -i your-key-pair.pem ec2-user@<instance-ip>

# Verify all tools are available
which UnrealEditor
echo $ANDROID_HOME
ls $GAMELIFT_SDK_ROOT
```

## Maintenance

Update the AMI periodically to include:
- Latest Unreal Engine patches
- Android SDK updates
- Security patches
- GameLift SDK updates

Recommended update frequency: Monthly or when major UE5 updates are released.

## Troubleshooting

**Issue: Unreal Engine build fails**
- Ensure all dependencies are installed
- Check disk space (minimum 150GB recommended)
- Verify clang and build tools are in PATH

**Issue: Android SDK not found**
- Verify ANDROID_HOME environment variable
- Check SDK installation in /opt/android-sdk
- Ensure NDK is installed

**Issue: GameLift SDK missing**
- Verify GAMELIFT_SDK_ROOT environment variable
- Check SDK extraction in /opt/GameLiftSDK
- Download latest SDK version if needed

## Cost Optimization

- Use spot instances for AMI creation (~70% cost savings)
- Terminate setup instance immediately after AMI creation
- Share AMI across team members to avoid duplicate setup
- Use smaller instance type for setup (t3.xlarge) if not testing builds

## Security Notes

- Never include AWS credentials in the AMI
- Remove SSH keys and bash history before creating AMI
- Use IAM roles for AWS access, not hardcoded credentials
- Keep AMI private unless sharing with specific AWS accounts
