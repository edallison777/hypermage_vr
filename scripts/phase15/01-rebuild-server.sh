#!/usr/bin/env bash
# 01-rebuild-server.sh — Phase 15: Rebuild UE5 Linux dedicated server with Phase 13/14 changes.
#
# Mirrors scripts/phase4/02-compile-server.sh.
# The AMI (ami-0c01dd20bfd8bb6a9) and unreal_build infrastructure already exist.
# This script launches a new build instance, pulls the latest code, rebuilds, and
# uploads a new HyperMageVRServer.zip to S3.
#
# New C++ in this build (vs Phase 4):
#   - HMVRPlayerState.h/cpp       — Cognito PlayerId replication
#   - AwsSigV4.h/cpp              — SigV4 HTTP signing
#   - SessionAPIClient.h/cpp      — real POST /session-summary + /interaction-events
#   - HMVRGameMode.cpp            — Login() decodes JWT sub → PlayerId
#   - HyperMageVR.Build.cs        — HTTP + OpenSSL dependencies
#
# Prerequisites:
#   - ami_id.auto.tfvars present (from Phase 4 / 01-create-ami.sh)
#   - AWS CLI configured with eu-west-1 access
#   - GITHUB_TOKEN env var set (or repo is public)
#
# Usage:
#   GITHUB_TOKEN=ghp_xxx ./scripts/phase15/01-rebuild-server.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-732231126129}"

echo "=== Phase 15 / Step 1: Rebuild UE5.3 Linux Server ==="

# ── 1. Verify AMI ID is available ─────────────────────────────────────────────
TFVARS="$TF_DIR/ami_id.auto.tfvars"
if [[ ! -f "$TFVARS" ]]; then
  echo "ERROR: $TFVARS not found. Phase 4 AMI must exist first." >&2
  exit 1
fi
AMI_ID=$(grep 'ami_id' "$TFVARS" | sed 's/.*= *"\(.*\)"/\1/')
echo "Using AMI: $AMI_ID"

# ── 2. Ensure unreal_build module is applied ──────────────────────────────────
echo ""
echo "--- Verifying unreal_build Terraform outputs ---"
cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1

S3_BUCKET=$(terraform output -raw build_s3_bucket)
LAUNCH_TEMPLATE_ID=$(terraform output -raw build_launch_template)
IAM_PROFILE=$(terraform output -raw build_iam_profile)

echo "S3 bucket      : $S3_BUCKET"
echo "Launch template: $LAUNCH_TEMPLATE_ID"
echo "IAM profile    : $IAM_PROFILE"

# Clear stale markers
aws s3 rm "s3://$S3_BUCKET/builds/latest/compile-success.txt" --region "$AWS_REGION" 2>/dev/null || true

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
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hypermage-vr-phase15-rebuild},{Key=Phase,Value=15}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID"

echo "Waiting for SSM agent..."
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

# ── 4. Run rebuild via SSM ────────────────────────────────────────────────────
echo ""
echo "--- Running server rebuild on $INSTANCE_ID (30-90 minutes) ---"

SCRIPT_FILE="$REPO_ROOT/.ssm-phase15-build-script.sh"
PARAMS_FILE="$REPO_ROOT/.ssm-phase15-build-params.json"

cat > "$SCRIPT_FILE" << ENDBUILDSCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME=/root
export DOTNET_CLI_HOME=/root
export DOTNET_NOLOGO=1
source /etc/profile.d/hypermage-build.sh 2>/dev/null || source /etc/environment || true

echo "=== Phase 15: HyperMage VR server rebuild ==="
echo "--- Disk space ---"
df -h /
echo "--- S3 write test ---"
echo "ok" | aws s3 cp - "s3://${S3_BUCKET}/builds/latest/build-start-phase15.txt" --region "${AWS_REGION}" \
  && echo "S3 write: OK" \
  || echo "S3 write: FAILED"

cd /build/workspace

echo "Cloning repository (latest with Phase 13/14 C++ changes)..."
git clone --depth 1 \
  "https://${GITHUB_TOKEN:-}${GITHUB_TOKEN:+@}github.com/edallison777/hypermage_vr.git" \
  HyperMageVR

cd HyperMageVR/UnrealProject

git config --global --add safe.directory '*' 2>/dev/null || true

echo "Setting up GameLift SDK..."
echo "  /opt/GameLiftSDK contents: \$(ls /opt/GameLiftSDK/)"

if [[ -f /opt/GameLiftSDK/setup.sh ]]; then
  echo "  Running setup.sh..."
  PREV_DIR=\$(pwd)
  cd /opt/GameLiftSDK
  bash setup.sh 2>&1 | tail -20
  cd "\$PREV_DIR"
fi

echo "  Outcome.h locations: \$(find /opt/GameLiftSDK -name 'Outcome.h' 2>/dev/null | tr '\n' ' ')"

echo "Installing GameLift Server SDK plugin..."
GAMELIFT_UPLUGIN=\$(find /opt/GameLiftSDK -name "GameLiftServerSDK.uplugin" -print -quit 2>/dev/null || echo "")
if [[ -n "\$GAMELIFT_UPLUGIN" ]]; then
  GAMELIFT_PLUGIN_DIR=\$(dirname "\$GAMELIFT_UPLUGIN")
  mkdir -p Plugins/GameLiftServerSDK
  cp -r "\$GAMELIFT_PLUGIN_DIR/." Plugins/GameLiftServerSDK/
  echo "  Outcome.h present: \$(find Plugins/GameLiftServerSDK -name 'Outcome.h' | head -1 || echo 'NOT FOUND')"
  echo "GameLift plugin installed."
else
  echo "ERROR: GameLiftServerSDK.uplugin not found under /opt/GameLiftSDK" >&2
  exit 1
fi

# Create Editor target if missing (needed for cook step)
if ! ls Source/*Editor.Target.cs 2>/dev/null | head -1 > /dev/null; then
  echo "No Editor target found — creating minimal one..."
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
fi

# Verify new Phase 13/14 source files are present
echo "--- Verifying new Phase 13/14 source files ---"
for f in Source/HyperMageVR/HMVRPlayerState.h Source/HyperMageVR/AwsSigV4.h Source/HyperMageVR/SessionAPIClient.h; do
  if [[ -f "\$f" ]]; then
    echo "  OK: \$f"
  else
    echo "  MISSING: \$f — git clone may not have latest code" >&2
    exit 1
  fi
done

chown -R ec2-user:ec2-user /build/workspace /build/output

SUDO_UAT="sudo -u ec2-user env HOME=/home/ec2-user PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin UE5_ROOT=/opt/UnrealEngine DOTNET_CLI_HOME=/home/ec2-user DOTNET_NOLOGO=1 /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh"
UAT_BASE="-project=/build/workspace/HyperMageVR/UnrealProject/HyperMageVR.uproject -platform=Linux -configuration=Development -server -noclient"

# ── Phase 1: Compile ──────────────────────────────────────────────────────────
echo "=== PHASE 1: Compile (includes HTTP + OpenSSL deps) ==="
set +e
\$SUDO_UAT BuildCookRun \$UAT_BASE -build -log 2>&1 | tee /build/compile.log
COMPILE_EXIT=\${PIPESTATUS[0]}
set -e

aws s3 cp /build/compile.log "s3://${S3_BUCKET}/builds/latest/compile-phase15.log" --region "${AWS_REGION}" || true

if [[ \$COMPILE_EXIT -ne 0 ]]; then
  echo "PHASE:COMPILE_FAILED (exit \$COMPILE_EXIT)"
  echo "Log: aws s3 cp s3://${S3_BUCKET}/builds/latest/compile-phase15.log ./compile.log --region ${AWS_REGION} && tail -100 ./compile.log"
  exit \$COMPILE_EXIT
fi
echo "ok" | aws s3 cp - "s3://${S3_BUCKET}/builds/latest/compile-success.txt" --region "${AWS_REGION}"
echo "PHASE:COMPILE_OK"

# ── Phase 2: Cook + Stage + Package ──────────────────────────────────────────
echo "=== PHASE 2: Cook + Stage + Package ==="
sudo dnf install -y atk 2>&1 | tail -3 || true

set +e
\$SUDO_UAT BuildCookRun \$UAT_BASE -cook -stage -package -archive -archivedirectory=/build/output -skipbuild -log 2>&1 | tee /build/cook.log
COOK_EXIT=\${PIPESTATUS[0]}
set -e

aws s3 cp /build/cook.log "s3://${S3_BUCKET}/builds/latest/cook-phase15.log" --region "${AWS_REGION}" || true

if [[ \$COOK_EXIT -ne 0 ]]; then
  echo "PHASE:COOK_FAILED (exit \$COOK_EXIT)"
  echo "Log: aws s3 cp s3://${S3_BUCKET}/builds/latest/cook-phase15.log ./cook.log --region ${AWS_REGION} && tail -100 ./cook.log"

  COMPILE_OK=\$(aws s3 ls "s3://${S3_BUCKET}/builds/latest/compile-success.txt" --region "${AWS_REGION}" >/dev/null 2>&1 && echo "yes" || echo "no")
  if [[ "\$COMPILE_OK" == "yes" ]]; then
    echo ""
    echo "=== Compile SUCCEEDED — cook FAILED. Instance ${INSTANCE_ID:-unknown} is still running. ==="
    echo "To retry cook without recompiling:"
    echo "  aws ssm start-session --target \$INSTANCE_ID --region ${AWS_REGION}"
    echo "  Then run the PHASE 2 command above manually."
  fi
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

echo "=== Phase 15 server rebuild complete ==="
aws s3 ls "s3://${S3_BUCKET}/builds/latest/"
ENDBUILDSCRIPT

# Encode the script as a JSON parameters file
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
  --comment "HyperMage VR Phase 15 server rebuild" \
  --query 'Command.CommandId' \
  --output text)

rm -f "$SCRIPT_FILE" "$PARAMS_FILE"

echo "SSM command ID: $COMMAND_ID"
echo "Waiting for build (up to 2 hours)..."

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
  echo "Build failed or timed out. Fetching SSM output..."
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

  COMPILE_OK=$(aws s3 ls "s3://$S3_BUCKET/builds/latest/compile-success.txt" \
    --region "$AWS_REGION" >/dev/null 2>&1 && echo "yes" || echo "no")
  if [[ "$COMPILE_OK" == "yes" ]]; then
    echo ""
    echo "=== Compile SUCCEEDED — cook FAILED. Instance $INSTANCE_ID still running. ==="
    echo "Connect to retry cook:"
    echo "  aws ssm start-session --target $INSTANCE_ID --region $AWS_REGION"
    echo "Terminate when done:"
    echo "  aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID"
  else
    echo "Compile failed. Terminating instance..."
    aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  fi
  exit 1
fi

echo ""
echo "=== Server rebuild complete: s3://$S3_BUCKET/builds/latest/HyperMageVRServer.zip ==="

# ── 5. Terminate build instance ───────────────────────────────────────────────
echo "Terminating build instance $INSTANCE_ID..."
aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
echo "Instance terminated."

echo ""
echo "Next step: run scripts/phase15/02-deploy-fleet.sh"
