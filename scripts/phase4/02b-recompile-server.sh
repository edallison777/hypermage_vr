#!/usr/bin/env bash
# 02b-recompile-server.sh — Recompile C++ only, reusing existing cooked content from S3.
#
# Use this instead of 02-compile-server.sh when only C++ source files changed
# (no asset/content changes) to avoid the ~1.5-2 hour cook step.
#
# What it does:
#   1. Launches a build EC2 instance (same AMI as before)
#   2. Downloads existing HyperMageVRServer.zip from S3 (cooked content)
#   3. Clones repo, compiles C++ only (-build, no -cook)
#   4. Replaces binaries in the extracted zip with freshly compiled ones
#   5. Rezips and uploads to S3, overwriting the previous build
#
# Prerequisites:
#   - HyperMageVRServer.zip already in S3 (run 02-compile-server.sh first)
#   - ami_id.auto.tfvars present (run 01-create-ami.sh first)
#   - GITHUB_TOKEN env var set (or repo is public)
#
# Usage:
#   GITHUB_TOKEN=ghp_xxx ./scripts/phase4/02b-recompile-server.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"

echo "=== Phase 4 / Step 2b: Recompile C++ (reuse cooked content) ==="

# ── 1. Verify prerequisites ───────────────────────────────────────────────────
TFVARS="$TF_DIR/ami_id.auto.tfvars"
if [[ ! -f "$TFVARS" ]]; then
  echo "ERROR: $TFVARS not found. Run 01-create-ami.sh first." >&2
  exit 1
fi
AMI_ID=$(grep 'ami_id' "$TFVARS" | sed 's/.*= *"\(.*\)"/\1/')
echo "Using AMI: $AMI_ID"

cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1
S3_BUCKET=$(terraform output -raw build_s3_bucket 2>/dev/null || true)
if [[ -z "$S3_BUCKET" ]]; then
  echo "ERROR: build_s3_bucket output not available." >&2
  exit 1
fi

BUILD_KEY="builds/latest/HyperMageVRServer.zip"
echo "Checking s3://$S3_BUCKET/$BUILD_KEY ..."
if ! aws s3 ls "s3://$S3_BUCKET/$BUILD_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ERROR: No existing build found. Run 02-compile-server.sh first." >&2
  exit 1
fi
echo "Existing build found — will reuse cooked content."

# ── 2. Get launch template from Terraform state ───────────────────────────────
LAUNCH_TEMPLATE_ID=$(terraform output -raw build_launch_template 2>/dev/null || true)
if [[ -z "$LAUNCH_TEMPLATE_ID" ]]; then
  echo "ERROR: build_launch_template output not available." >&2
  exit 1
fi

# ── 3. Launch build instance ──────────────────────────────────────────────────
echo ""
echo "--- Launching build instance ---"
SUBNET_ID=$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=default-for-az,Values=true" \
  --query 'Subnets[0].SubnetId' \
  --output text)

INSTANCE_ID=$(aws ec2 run-instances \
  --region "$AWS_REGION" \
  --launch-template "LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=\$Latest" \
  --subnet-id "$SUBNET_ID" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hypermage-vr-recompile},{Key=Phase,Value=4b}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

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

# ── 4. Run recompile via SSM ──────────────────────────────────────────────────
echo ""
echo "--- Running recompile on $INSTANCE_ID (30-60 minutes) ---"

SCRIPT_FILE="$REPO_ROOT/.ssm-recompile-script.sh"
PARAMS_FILE="$REPO_ROOT/.ssm-recompile-params.json"

cat > "$SCRIPT_FILE" << ENDSCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME=/root
export DOTNET_CLI_HOME=/root
export DOTNET_NOLOGO=1
source /etc/profile.d/hypermage-build.sh 2>/dev/null || source /etc/environment || true

echo "=== HyperMage VR C++ recompile ==="
df -h /

# ── Download existing build (cooked content) ──────────────────────────────────
echo "Downloading existing build from S3..."
mkdir -p /build/existing /build/output
aws s3 cp "s3://${S3_BUCKET}/${BUILD_KEY}" /build/existing.zip --region "${AWS_REGION}"
echo "Extracting..."
cd /build/existing
unzip -q /build/existing.zip
echo "Extracted. Binary dir:"
find /build/existing -name "*.sh" -o -name "HyperMageVRServer" -not -name "*.sh" | head -10

# ── Clone repo ────────────────────────────────────────────────────────────────
echo "Cloning repository..."
cd /build/workspace
git clone --depth 1 \
  "https://${GITHUB_TOKEN:-}${GITHUB_TOKEN:+@}github.com/edallison777/hypermage_vr.git" \
  HyperMageVR
cd HyperMageVR/UnrealProject
git config --global --add safe.directory '*' 2>/dev/null || true

# ── Run setup.sh to stage C++ SDK headers/libs into the plugin ───────────────
echo "Running GameLift SDK setup.sh..."
cd /opt/GameLiftSDK
bash setup.sh 2>&1 | tail -20
cd /build/workspace/HyperMageVR/UnrealProject

# ── Install GameLift plugin ────────────────────────────────────────────────────
echo "Setting up GameLift SDK plugin..."
GAMELIFT_UPLUGIN=\$(find /opt/GameLiftSDK -name "GameLiftServerSDK.uplugin" -print -quit 2>/dev/null || echo "")
if [[ -n "\$GAMELIFT_UPLUGIN" ]]; then
  GAMELIFT_PLUGIN_DIR=\$(dirname "\$GAMELIFT_UPLUGIN")
  mkdir -p Plugins/GameLiftServerSDK
  cp -r "\$GAMELIFT_PLUGIN_DIR/." Plugins/GameLiftServerSDK/
  echo "GameLift plugin installed."
else
  echo "ERROR: GameLiftServerSDK.uplugin not found under /opt/GameLiftSDK" >&2
  exit 1
fi

# ── Ensure Editor target exists (needed for UAT even when skipping cook) ──────
if ! ls Source/*Editor.Target.cs 2>/dev/null | head -1 > /dev/null; then
  cat > "Source/HyperMageVREditor.Target.cs" << CSEOF
using UnrealBuildTool;
public class HyperMageVREditorTarget : TargetRules {
    public HyperMageVREditorTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_1;
        ExtraModuleNames.Add("HyperMageVR");
    }
}
CSEOF
fi

chown -R ec2-user:ec2-user /build/workspace /build/output

SUDO_UAT="sudo -u ec2-user env HOME=/home/ec2-user PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin UE5_ROOT=/opt/UnrealEngine DOTNET_CLI_HOME=/home/ec2-user DOTNET_NOLOGO=1 /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh"
UAT_BASE="-project=/build/workspace/HyperMageVR/UnrealProject/HyperMageVR.uproject -platform=Linux -configuration=Development -server -noclient"

# ── Compile C++ only ──────────────────────────────────────────────────────────
echo "=== Compiling C++ ==="
set +e
\$SUDO_UAT BuildCookRun \$UAT_BASE -build -log 2>&1 | tee /build/compile.log
COMPILE_EXIT=\${PIPESTATUS[0]}
set -e

aws s3 cp /build/compile.log "s3://${S3_BUCKET}/builds/latest/compile.log" --region "${AWS_REGION}" || true

if [[ \$COMPILE_EXIT -ne 0 ]]; then
  echo "COMPILE FAILED (exit \$COMPILE_EXIT)"
  exit \$COMPILE_EXIT
fi
echo "Compile succeeded."

# ── Replace binaries in extracted zip ────────────────────────────────────────
echo "Replacing binaries..."
NEW_BIN_DIR="/build/workspace/HyperMageVR/UnrealProject/Binaries/Linux"
EXISTING_BIN_DIR=\$(find /build/existing -path "*/Binaries/Linux" -type d | head -1 || echo "")

if [[ -z "\$EXISTING_BIN_DIR" ]]; then
  echo "ERROR: Could not find Binaries/Linux in extracted zip." >&2
  ls -la /build/existing/
  exit 1
fi

echo "  New binaries: \$NEW_BIN_DIR"
echo "  Replacing in: \$EXISTING_BIN_DIR"
ls "\$NEW_BIN_DIR/"
cp "\$NEW_BIN_DIR/"* "\$EXISTING_BIN_DIR/"
echo "Binaries replaced."

# ── Rezip and upload ──────────────────────────────────────────────────────────
echo "Rezipping..."
cd /build/existing
zip -r /build/output/HyperMageVRServer.zip .

echo "Uploading to S3..."
aws s3 cp /build/output/HyperMageVRServer.zip \
  "s3://${S3_BUCKET}/builds/latest/HyperMageVRServer.zip" \
  --region "${AWS_REGION}"

echo "=== Recompile complete ==="
aws s3 ls "s3://${S3_BUCKET}/builds/latest/"
ENDSCRIPT

SCRIPT_WIN=$(cygpath -w "$SCRIPT_FILE")
PARAMS_WIN=$(cygpath -w "$PARAMS_FILE")
SCRIPT_WIN="$SCRIPT_WIN" PARAMS_WIN="$PARAMS_WIN" node -e "
const fs = require('fs');
const script = fs.readFileSync(process.env.SCRIPT_WIN, 'utf8');
fs.writeFileSync(process.env.PARAMS_WIN, JSON.stringify({commands: [script], executionTimeout: ['10800']}));
"

COMMAND_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "file://$PARAMS_WIN" \
  --timeout-seconds 10800 \
  --comment "HyperMage VR C++ recompile" \
  --query 'Command.CommandId' \
  --output text)

rm -f "$SCRIPT_FILE" "$PARAMS_FILE"

echo "SSM command ID: $COMMAND_ID"
echo "Waiting for recompile to complete (up to 60 minutes)..."

MAX_WAIT=10800
WAITED=0
INTERVAL=30
STATUS="InProgress"
while [[ "$STATUS" == "InProgress" || "$STATUS" == "Pending" ]]; do
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "ERROR: Recompile timed out after ${MAX_WAIT}s." >&2
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
  echo "Recompile failed. Fetching output..."
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
  echo "Instance $INSTANCE_ID left running for inspection."
  exit 1
fi

# ── 5. Terminate instance ─────────────────────────────────────────────────────
echo "Terminating build instance $INSTANCE_ID..."
aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
echo "Instance terminated."

echo ""
echo "=== Recompile complete. New build at s3://$S3_BUCKET/builds/latest/HyperMageVRServer.zip ==="
echo "Next step: run scripts/phase4/03-deploy-gamelift.sh"
