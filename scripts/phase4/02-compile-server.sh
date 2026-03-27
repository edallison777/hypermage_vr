#!/usr/bin/env bash
# 02-compile-server.sh — Apply unreal_build module, launch a build EC2, compile the
# Linux dedicated server, and upload HyperMageVRServer.zip to S3.
#
# Prerequisites:
#   - AMI ID written to Infra/environments/dev/ami_id.auto.tfvars (run 01-create-ami.sh first)
#   - Terraform >= 1.5 and AWS CLI configured
#   - GitHub repo accessible from the build instance (or GITHUB_TOKEN env var set)
#   - SSM Session Manager plugin installed locally
#
# Usage:
#   GITHUB_TOKEN=ghp_xxx ./scripts/phase4/02-compile-server.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-732231126129}"
PROJECT_REPO="${PROJECT_REPO:-https://github.com/edallison777/hypermage_vr.git}"

echo "=== Phase 4 / Step 2: Compile UE5.3 Linux Server ==="

# ── 1. Verify AMI ID is available ─────────────────────────────────────────────
TFVARS="$TF_DIR/ami_id.auto.tfvars"
if [[ ! -f "$TFVARS" ]]; then
  echo "ERROR: $TFVARS not found. Run 01-create-ami.sh first." >&2
  exit 1
fi
AMI_ID=$(grep 'ami_id' "$TFVARS" | sed 's/.*= *"\(.*\)"/\1/')
echo "Using AMI: $AMI_ID"

# ── 2. Apply unreal_build Terraform module ────────────────────────────────────
echo ""
echo "--- Applying unreal_build Terraform module ---"
cd "$TF_DIR"
terraform init -reconfigure
terraform apply \
  -target=module.unreal_build \
  -auto-approve

S3_BUCKET=$(terraform output -raw build_s3_bucket)
LAUNCH_TEMPLATE_ID=$(terraform output -raw build_launch_template)
IAM_PROFILE=$(terraform output -raw build_iam_profile)

echo "S3 bucket      : $S3_BUCKET"
echo "Launch template: $LAUNCH_TEMPLATE_ID"
echo "IAM profile    : $IAM_PROFILE"

# ── 3. Launch build instance via launch template ──────────────────────────────
echo ""
echo "--- Launching build instance ---"

# Use default subnet
SUBNET_ID=$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=default-for-az,Values=true" \
  --query 'Subnets[0].SubnetId' \
  --output text)

INSTANCE_ID=$(aws ec2 run-instances \
  --region "$AWS_REGION" \
  --launch-template "LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=\$Latest" \
  --subnet-id "$SUBNET_ID" \
  --iam-instance-profile "Name=$IAM_PROFILE" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hypermage-vr-server-build},{Key=Phase,Value=4}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID"

echo "Waiting for SSM agent to be ready..."
sleep 60  # Give SSM agent time to register

# ── 4. Run build commands via SSM ─────────────────────────────────────────────
echo ""
echo "--- Running server build on $INSTANCE_ID (this takes 30-90 minutes) ---"

BUILD_COMMANDS=$(cat <<HEREDOC
#!/usr/bin/env bash
set -euo pipefail
source /etc/profile.d/hypermage-build.sh 2>/dev/null || source /etc/environment || true

echo "=== Starting HyperMage VR server build ==="
cd /build/workspace

# Clone repository
echo "Cloning repository..."
git clone --depth 1 \
  "https://${GITHUB_TOKEN:-}${GITHUB_TOKEN:+@}github.com/edallison777/hypermage_vr.git" \
  HyperMageVR

cd HyperMageVR/UnrealProject

# Build Linux dedicated server
echo "Building Linux server (30-90 minutes)..."
\$UE5_ROOT/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun \
  -project="\$(pwd)/HyperMageVR.uproject" \
  -platform=Linux \
  -configuration=Development \
  -cook -build -stage -package -server -noclient \
  -archive -archivedirectory=/build/output \
  -log

# Package into zip
echo "Packaging server build..."
cd /build/output/LinuxServer
zip -r /build/output/HyperMageVRServer.zip .

# Upload to S3
echo "Uploading to S3..."
aws s3 cp /build/output/HyperMageVRServer.zip \
  "s3://${S3_BUCKET}/builds/latest/HyperMageVRServer.zip" \
  --region "${AWS_REGION}"

echo "=== Server build complete ==="
aws s3 ls "s3://${S3_BUCKET}/builds/latest/"
HEREDOC
)

COMMAND_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"$BUILD_COMMANDS\"]" \
  --timeout-seconds 7200 \
  --comment "HyperMage VR server build" \
  --query 'Command.CommandId' \
  --output text)

echo "SSM command ID: $COMMAND_ID"
echo "Waiting for build to complete (up to 2 hours)..."

# Poll for completion
MAX_WAIT=7200
WAITED=0
INTERVAL=60
STATUS="InProgress"
while [[ "$STATUS" == "InProgress" || "$STATUS" == "Pending" ]]; do
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "ERROR: Build timed out after ${MAX_WAIT}s." >&2
    break
  fi
  sleep $INTERVAL
  WAITED=$((WAITED + INTERVAL))
  STATUS=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' \
    --output text 2>/dev/null || echo "InProgress")
  echo "  [${WAITED}s] Status: $STATUS"
done

if [[ "$STATUS" != "Success" ]]; then
  echo "Build failed. Fetching output..."
  aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardErrorContent' \
    --output text
  echo "Terminating instance..."
  aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  exit 1
fi

echo ""
echo "=== Server build uploaded to s3://$S3_BUCKET/builds/latest/HyperMageVRServer.zip ==="

# ── 5. Terminate build instance ───────────────────────────────────────────────
echo "Terminating build instance $INSTANCE_ID..."
aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
echo "Instance terminated."

echo ""
echo "Next step: run scripts/phase4/03-deploy-gamelift.sh"
