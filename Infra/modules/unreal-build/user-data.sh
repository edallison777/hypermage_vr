#!/bin/bash
# User data script for Unreal Engine build instances
# This script runs on instance launch to configure the build environment

set -e

# Variables from Terraform
S3_BUCKET="${s3_bucket}"
AWS_REGION="${aws_region}"
ENVIRONMENT="${environment}"

# Configure CloudWatch Logs agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/unreal-build.log",
            "log_group_name": "/aws/ec2/unreal-build/$ENVIRONMENT",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
EOF

# Start CloudWatch Logs agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

# Create build log file
touch /var/log/unreal-build.log
chmod 644 /var/log/unreal-build.log

# Log instance startup
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - Unreal build instance started" >> /var/log/unreal-build.log
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - Instance ID: $(ec2-metadata --instance-id | cut -d ' ' -f 2)" >> /var/log/unreal-build.log
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - S3 Bucket: $S3_BUCKET" >> /var/log/unreal-build.log
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - AWS Region: $AWS_REGION" >> /var/log/unreal-build.log
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - Environment: $ENVIRONMENT" >> /var/log/unreal-build.log

# Set environment variables for build scripts
export UE5_ROOT="/opt/UnrealEngine"
export ANDROID_HOME="/opt/android-sdk"
export GAMELIFT_SDK_ROOT="/opt/GameLiftSDK"

# Create build workspace
mkdir -p /build/workspace
chmod 755 /build/workspace

# Signal that instance is ready
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - Instance ready for builds" >> /var/log/unreal-build.log

# Note: Actual build commands will be executed via SSM or SSH by UnrealMCP adapter
# This script only prepares the environment
