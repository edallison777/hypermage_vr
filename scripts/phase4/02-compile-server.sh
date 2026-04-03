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

# Clear previous compile-success marker so a stale marker never masks a fresh compile failure
aws s3 rm "s3://$S3_BUCKET/builds/latest/compile-success.txt" --region "$AWS_REGION" 2>/dev/null || true

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
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hypermage-vr-server-build},{Key=Phase,Value=4}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID"

echo "Waiting for SSM agent to be ready..."
SSM_WAIT=0
SSM_MAX=300
until aws ssm describe-instance-information \
    --region "$AWS_REGION" \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' \
    --output text 2>/dev/null | grep -q "Online"; do
  if [[ $SSM_WAIT -ge $SSM_MAX ]]; then
    echo "ERROR: SSM agent did not come online within ${SSM_MAX}s." >&2
    aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
    exit 1
  fi
  sleep 15
  SSM_WAIT=$((SSM_WAIT + 15))
  echo "  [${SSM_WAIT}s] Waiting for SSM..."
done
echo "SSM agent online."

# ── 4. Run build commands via SSM ─────────────────────────────────────────────
echo ""
echo "--- Running server build on $INSTANCE_ID (this takes 30-90 minutes) ---"

SCRIPT_FILE="$REPO_ROOT/.ssm-build-script.sh"
PARAMS_FILE="$REPO_ROOT/.ssm-build-params.json"

cat > "$SCRIPT_FILE" << ENDBUILDSCRIPT
#!/usr/bin/env bash
set -euo pipefail
# SSM runs without a login shell — set home dirs required by .NET/Unreal toolchain
export HOME=/root
export DOTNET_CLI_HOME=/root
export DOTNET_NOLOGO=1
source /etc/profile.d/hypermage-build.sh 2>/dev/null || source /etc/environment || true

echo "=== Starting HyperMage VR server build ==="
echo "--- Disk space ---"
df -h /
echo "--- S3 write test ---"
echo "ok" | aws s3 cp - "s3://${S3_BUCKET}/builds/latest/build-start.txt" --region "${AWS_REGION}" \
  && echo "S3 write: OK" \
  || echo "S3 write: FAILED"

cd /build/workspace

echo "Cloning repository..."
git clone --depth 1 \
  "https://${GITHUB_TOKEN:-}${GITHUB_TOKEN:+@}github.com/edallison777/hypermage_vr.git" \
  HyperMageVR

cd HyperMageVR/UnrealProject

# Fix safe.directory so git/find work when running as root on ec2-user-owned dirs
git config --global --add safe.directory '*' 2>/dev/null || true

echo "Setting up GameLift SDK..."
echo "  /opt/GameLiftSDK contents: \$(ls /opt/GameLiftSDK/)"

# Run the repo's own setup script if present — it wires GameLiftServerSDK/ into the plugin ThirdParty
if [[ -f /opt/GameLiftSDK/setup.sh ]]; then
  echo "  Running setup.sh..."
  PREV_DIR=\$(pwd)
  cd /opt/GameLiftSDK
  bash setup.sh 2>&1 | tail -20
  cd "\$PREV_DIR"
  echo "  setup.sh complete (back in \$(pwd))."
fi

# Verify headers are now in place
echo "  Outcome.h locations: \$(find /opt/GameLiftSDK -name 'Outcome.h' 2>/dev/null | tr '\n' ' ')"

# Install GameLift UE plugin and wire the C++ SDK into its ThirdParty directory
echo "Installing GameLift Server SDK plugin..."
GAMELIFT_UPLUGIN=\$(find /opt/GameLiftSDK -name "GameLiftServerSDK.uplugin" -print -quit 2>/dev/null || echo "")
if [[ -n "\$GAMELIFT_UPLUGIN" ]]; then
  GAMELIFT_PLUGIN_DIR=\$(dirname "\$GAMELIFT_UPLUGIN")
  mkdir -p Plugins/GameLiftServerSDK
  cp -r "\$GAMELIFT_PLUGIN_DIR/." Plugins/GameLiftServerSDK/

  # Find where the Build.cs expects the C++ SDK (look for PublicIncludePaths in Build.cs)
  PLUGIN_THIRDPARTY_SDK=\$(grep -r "ThirdParty" Plugins/GameLiftServerSDK/Source/GameLiftServerSDK/*.Build.cs 2>/dev/null \
    | grep -i "gamelift" | grep "Path.Combine" | head -1 \
    | sed 's/.*Path.Combine(\(.*\))/\1/' || echo "")
  # Pull pre-built ThirdParty (headers + libs) from the release ZIP if present
  # Verify headers are accessible via the plugin's own Source/ (no separate ThirdParty copy needed)
  echo "  Outcome.h present: \$(find Plugins/GameLiftServerSDK -name 'Outcome.h' | head -1 || echo 'NOT FOUND')"
  echo "GameLift plugin installed."
else
  echo "ERROR: GameLiftServerSDK.uplugin not found under /opt/GameLiftSDK" >&2
  exit 1
fi

# UAT requires an Editor target to cook content — create one if missing
if ! ls Source/*Editor.Target.cs 2>/dev/null | head -1 > /dev/null; then
  echo "No Editor target found — creating minimal one for cooking..."
  mkdir -p Source
  # Use primary module name if a .Build.cs exists, otherwise Blueprint-only project
  PRIMARY_MODULE=\$(ls Source/*.Build.cs 2>/dev/null | grep -iv editor | head -1 | xargs -I{} basename {} .Build.cs || echo "")
  if [[ -n "\$PRIMARY_MODULE" ]]; then
    EXTRA_MODULES="        ExtraModuleNames.Add(\\\"\$PRIMARY_MODULE\\\");"
  else
    EXTRA_MODULES=""
  fi
  cat > "Source/HyperMageVREditor.Target.cs" << CSEOF
using UnrealBuildTool;
public class HyperMageVREditorTarget : TargetRules {
    public HyperMageVREditorTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_1;
\$EXTRA_MODULES
    }
}
CSEOF
  echo "Created Source/HyperMageVREditor.Target.cs"
fi

# UnrealEditor (cook step) refuses to run as root — chown workspace to ec2-user first
chown -R ec2-user:ec2-user /build/workspace /build/output

SUDO_UAT="sudo -u ec2-user env HOME=/home/ec2-user PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin UE5_ROOT=/opt/UnrealEngine DOTNET_CLI_HOME=/home/ec2-user DOTNET_NOLOGO=1 /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh"
UAT_BASE="-project=/build/workspace/HyperMageVR/UnrealProject/HyperMageVR.uproject -platform=Linux -configuration=Development -server -noclient"

# ── Phase 1: Compile (30-90 minutes) ─────────────────────────────────────────
echo "=== PHASE 1: Compile ==="
set +e
\$SUDO_UAT BuildCookRun \$UAT_BASE -build -log 2>&1 | tee /build/compile.log
COMPILE_EXIT=\${PIPESTATUS[0]}
set -e

aws s3 cp /build/compile.log "s3://${S3_BUCKET}/builds/latest/compile.log" --region "${AWS_REGION}" || true

if [[ \$COMPILE_EXIT -ne 0 ]]; then
  echo "PHASE:COMPILE_FAILED (exit \$COMPILE_EXIT). Log: s3://${S3_BUCKET}/builds/latest/compile.log"
  exit \$COMPILE_EXIT
fi
echo "ok" | aws s3 cp - "s3://${S3_BUCKET}/builds/latest/compile-success.txt" --region "${AWS_REGION}"
echo "PHASE:COMPILE_OK"

# ── Phase 2: Cook + Stage + Package ──────────────────────────────────────────
echo "=== PHASE 2: Cook + Stage + Package ==="
# Bridge plugin requires libatk (GUI lib) which isn't installed by default on headless AL2023
sudo dnf install -y atk 2>&1 | tail -3 || true

set +e
\$SUDO_UAT BuildCookRun \$UAT_BASE -cook -stage -package -archive -archivedirectory=/build/output -skipbuild -log 2>&1 | tee /build/cook.log
COOK_EXIT=\${PIPESTATUS[0]}
set -e

aws s3 cp /build/cook.log "s3://${S3_BUCKET}/builds/latest/cook.log" --region "${AWS_REGION}" || true

if [[ \$COOK_EXIT -ne 0 ]]; then
  echo "PHASE:COOK_FAILED (exit \$COOK_EXIT). Log: s3://${S3_BUCKET}/builds/latest/cook.log"
  exit \$COOK_EXIT
fi
echo "PHASE:ALL_OK"

echo "Packaging server build..."
cd /build/output/LinuxServer
zip -r /build/output/HyperMageVRServer.zip .

echo "Uploading to S3..."
aws s3 cp /build/output/HyperMageVRServer.zip \
  "s3://${S3_BUCKET}/builds/latest/HyperMageVRServer.zip" \
  --region "${AWS_REGION}"

echo "=== Server build complete ==="
aws s3 ls "s3://${S3_BUCKET}/builds/latest/"
ENDBUILDSCRIPT

# Encode the script as a JSON parameters file to avoid CLI multiline parsing issues
# Use cygpath to convert Git Bash paths to Windows paths for Node.js
SCRIPT_WIN=$(cygpath -w "$SCRIPT_FILE")
PARAMS_WIN=$(cygpath -w "$PARAMS_FILE")
SCRIPT_WIN="$SCRIPT_WIN" PARAMS_WIN="$PARAMS_WIN" node -e "
const fs = require('fs');
const script = fs.readFileSync(process.env.SCRIPT_WIN, 'utf8');
fs.writeFileSync(process.env.PARAMS_WIN, JSON.stringify({commands: [script], executionTimeout: ['7200']}));
"

COMMAND_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "file://$PARAMS_WIN" \
  --timeout-seconds 7200 \
  --comment "HyperMage VR server build" \
  --query 'Command.CommandId' \
  --output text)

rm -f "$SCRIPT_FILE" "$PARAMS_FILE"

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
  echo "Build failed. Fetching SSM output..."
  aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardOutputContent' \
    --output text
  aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardErrorContent' \
    --output text

  # If compile succeeded and only cook failed, keep the instance alive for iteration
  COMPILE_OK=$(aws s3 ls "s3://$S3_BUCKET/builds/latest/compile-success.txt" \
    --region "$AWS_REGION" >/dev/null 2>&1 && echo "yes" || echo "no")

  if [[ "$COMPILE_OK" == "yes" ]]; then
    echo ""
    echo "=== Compile SUCCEEDED — cook FAILED. Instance $INSTANCE_ID is still running. ==="
    echo "Cook log: aws s3 cp s3://$S3_BUCKET/builds/latest/cook.log ./cook.log --region $AWS_REGION && tail -100 ./cook.log"
    echo ""
    echo "To retry the cook without recompiling, open an SSM session:"
    echo "  aws ssm start-session --target $INSTANCE_ID --region $AWS_REGION"
    echo ""
    echo "Then in the session run:"
    echo "  sudo -u ec2-user env HOME=/home/ec2-user UE5_ROOT=/opt/UnrealEngine DOTNET_CLI_HOME=/home/ec2-user DOTNET_NOLOGO=1 \\"
    echo "    /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun \\"
    echo "    -project=/build/workspace/HyperMageVR/UnrealProject/HyperMageVR.uproject \\"
    echo "    -platform=Linux -configuration=Development -server -noclient \\"
    echo "    -cook -stage -package -archive -archivedirectory=/build/output -skipbuild -log \\"
    echo "    2>&1 | tee /build/cook.log"
    echo ""
    echo "Terminate when done: aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID"
  else
    echo "Compile failed. Terminating instance..."
    aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  fi
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
