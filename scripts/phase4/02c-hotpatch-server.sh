#!/usr/bin/env bash
# 02c-hotpatch-server.sh — Incremental C++ recompile on a persistent "warm" build instance.
#
# WHY THIS EXISTS:
#   02-compile-server.sh and 02b-recompile-server.sh both do a fresh `git clone` every run,
#   so UBT always starts cold (30-60 min). UBT is incremental when the workspace is preserved —
#   a small C++ change recompiles in 5-15 min instead of an hour.
#
# HOW IT WORKS:
#   First run  — launches instance, clones repo, installs GameLift plugin, full compile.
#   Later runs — finds the running instance by ID (stored in .warm-build-instance),
#                does `git pull`, runs UBT (only changed files recompile), swaps binaries, uploads.
#
# IMPORTANT: push your C++ changes to GitHub before running this script.
#   The instance pulls from the remote, so unpushed local changes are not picked up.
#
# INSTANCE TYPE NOTE:
#   The launch template defaults to g4dn.xlarge (4 vCPUs). For compile-only work a CPU-
#   optimised instance is faster and cheaper. Override with HOTPATCH_INSTANCE_TYPE:
#     HOTPATCH_INSTANCE_TYPE=c5.4xlarge GITHUB_TOKEN=ghp_xxx ./02c-hotpatch-server.sh
#   c5.4xlarge (16 vCPUs) typically cuts full compile from ~60 min to ~15 min.
#   c5.9xlarge (36 vCPUs) cuts it further to ~8 min.
#
# WARM INSTANCE LIFECYCLE:
#   The instance keeps running after this script exits (that's the point).
#   When you're done iterating and have a good build, run:
#     ./scripts/phase4/02c-stop-warm-instance.sh
#
# Prerequisites:
#   - HyperMageVRServer.zip in S3 (run 02-compile-server.sh first to get cooked content)
#   - ami_id.auto.tfvars present
#   - GITHUB_TOKEN env var set (or repo is public)
#
# Usage:
#   GITHUB_TOKEN=ghp_xxx ./scripts/phase4/02c-hotpatch-server.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"
INSTANCE_FILE="$REPO_ROOT/.warm-build-instance"
HOTPATCH_INSTANCE_TYPE="${HOTPATCH_INSTANCE_TYPE:-}"  # empty = use launch template default

echo "=== Phase 4 / Step 2c: Incremental C++ hotpatch ==="

# ── Prereq checks ─────────────────────────────────────────────────────────────
TFVARS="$TF_DIR/ami_id.auto.tfvars"
if [[ ! -f "$TFVARS" ]]; then
  echo "ERROR: $TFVARS not found. Run 01-create-ami.sh first." >&2
  exit 1
fi
AMI_ID=$(grep 'ami_id' "$TFVARS" | sed 's/.*= *"\(.*\)"/\1/')
echo "AMI: $AMI_ID"

cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1
S3_BUCKET=$(terraform output -raw build_s3_bucket 2>/dev/null || true)
LAUNCH_TEMPLATE_ID=$(terraform output -raw build_launch_template 2>/dev/null || true)
if [[ -z "$S3_BUCKET" || -z "$LAUNCH_TEMPLATE_ID" ]]; then
  echo "ERROR: Terraform outputs missing. Run 02-compile-server.sh first." >&2
  exit 1
fi

BUILD_KEY="builds/latest/HyperMageVRServer.zip"
if ! aws s3 ls "s3://$S3_BUCKET/$BUILD_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ERROR: No existing build found at s3://$S3_BUCKET/$BUILD_KEY" >&2
  echo "       Run 02-compile-server.sh first to create cooked content." >&2
  exit 1
fi

# ── Find or launch warm instance ──────────────────────────────────────────────
INSTANCE_ID=""
IS_WARM=false

if [[ -f "$INSTANCE_FILE" ]]; then
  CANDIDATE=$(cat "$INSTANCE_FILE" | tr -d '[:space:]')
  STATE=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --instance-ids "$CANDIDATE" \
    --query 'Reservations[0].Instances[0].State.Name' \
    --output text 2>/dev/null || echo "not-found")
  if [[ "$STATE" == "running" ]]; then
    INSTANCE_ID="$CANDIDATE"
    IS_WARM=true
    echo "Warm instance found: $INSTANCE_ID (state: running)"
  else
    echo "Stored instance $CANDIDATE is '$STATE' — launching a new one."
    rm -f "$INSTANCE_FILE"
  fi
fi

if [[ -z "$INSTANCE_ID" ]]; then
  echo ""
  echo "--- Launching new build instance ---"
  SUBNET_ID=$(aws ec2 describe-subnets \
    --region "$AWS_REGION" \
    --filters "Name=default-for-az,Values=true" \
    --query 'Subnets[0].SubnetId' \
    --output text)

  # Build run-instances args — optionally override the instance type from the launch template
  RUN_ARGS=(
    --region "$AWS_REGION"
    --launch-template "LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=\$Latest"
    --subnet-id "$SUBNET_ID"
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hypermage-vr-hotpatch},{Key=Phase,Value=4c}]'
    --query 'Instances[0].InstanceId'
    --output text
  )
  if [[ -n "$HOTPATCH_INSTANCE_TYPE" ]]; then
    RUN_ARGS+=(--instance-type "$HOTPATCH_INSTANCE_TYPE")
    echo "Instance type override: $HOTPATCH_INSTANCE_TYPE"
  fi

  INSTANCE_ID=$(aws ec2 run-instances "${RUN_ARGS[@]}")
  echo "Launched: $INSTANCE_ID"
  echo "$INSTANCE_ID" > "$INSTANCE_FILE"

  echo "Waiting for instance to be running..."
  aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

  echo "Waiting for SSM agent..."
  SSM_WAIT=0
  until aws ssm describe-instance-information \
      --region "$AWS_REGION" \
      --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
      --query 'InstanceInformationList[0].PingStatus' \
      --output text 2>/dev/null | grep -q "Online"; do
    if [[ $SSM_WAIT -ge 300 ]]; then
      echo "ERROR: SSM agent timed out." >&2
      aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
      rm -f "$INSTANCE_FILE"
      exit 1
    fi
    sleep 15
    SSM_WAIT=$((SSM_WAIT + 15))
    echo "  [${SSM_WAIT}s] waiting..."
  done
  echo "SSM online."
fi

# ── Build the SSM command ──────────────────────────────────────────────────────
# Two paths: cold (first run, workspace absent) and warm (git pull only).
# UBT's Intermediate/ cache is the key — preserving it makes subsequent compiles incremental.

echo ""
if $IS_WARM; then
  echo "--- Warm path: git pull + incremental UBT compile ---"
else
  echo "--- Cold path: clone + GameLift setup + full UBT compile ---"
fi

SCRIPT_FILE="$REPO_ROOT/.ssm-hotpatch-script.sh"
PARAMS_FILE="$REPO_ROOT/.ssm-hotpatch-params.json"

cat > "$SCRIPT_FILE" << ENDSCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME=/root
export DOTNET_CLI_HOME=/root
export DOTNET_NOLOGO=1
source /etc/profile.d/hypermage-build.sh 2>/dev/null || source /etc/environment || true

WORKSPACE=/build/workspace/HyperMageVR/UnrealProject
SUDO_UAT="sudo -u ec2-user env HOME=/home/ec2-user PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin UE5_ROOT=/opt/UnrealEngine DOTNET_CLI_HOME=/home/ec2-user DOTNET_NOLOGO=1 /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh"
UAT_BASE="-project=\$WORKSPACE/HyperMageVR.uproject -platform=Linux -configuration=Development -server -noclient"

echo "=== Disk space ==="
df -h /

if [[ "${IS_WARM}" == "true" && -d "\$WORKSPACE" ]]; then
  # ── WARM PATH: incremental ────────────────────────────────────────────────────
  echo "=== Warm path: git pull ==="
  cd /build/workspace/HyperMageVR
  git config --global --add safe.directory '*' 2>/dev/null || true
  git pull --ff-only 2>&1
  echo "Pull complete."
else
  # ── COLD PATH: fresh clone + setup ───────────────────────────────────────────
  echo "=== Cold path: setting up workspace ==="
  mkdir -p /build/workspace /build/output
  cd /build/workspace

  echo "Cloning repository..."
  git config --global --add safe.directory '*' 2>/dev/null || true
  git clone --depth 1 \
    "https://${GITHUB_TOKEN:-}${GITHUB_TOKEN:+@}github.com/edallison777/hypermage_vr.git" \
    HyperMageVR

  cd HyperMageVR/UnrealProject

  echo "Running GameLift SDK setup.sh..."
  if [[ -f /opt/GameLiftSDK/setup.sh ]]; then
    cd /opt/GameLiftSDK && bash setup.sh 2>&1 | tail -20
    cd /build/workspace/HyperMageVR/UnrealProject
  fi

  echo "Installing GameLift plugin..."
  GAMELIFT_UPLUGIN=\$(find /opt/GameLiftSDK -name "GameLiftServerSDK.uplugin" -print -quit 2>/dev/null || echo "")
  if [[ -n "\$GAMELIFT_UPLUGIN" ]]; then
    mkdir -p Plugins/GameLiftServerSDK
    cp -r "\$(dirname \$GAMELIFT_UPLUGIN)/." Plugins/GameLiftServerSDK/
    echo "Plugin installed."
  else
    echo "ERROR: GameLiftServerSDK.uplugin not found." >&2
    exit 1
  fi

  # Editor target needed by UAT even for compile-only
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
fi

# ── Incremental compile (both paths) ─────────────────────────────────────────
echo "=== Compiling C++ (incremental if warm) ==="
chown -R ec2-user:ec2-user /build/workspace /build/output 2>/dev/null || true

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

# ── Swap binaries into existing zip ───────────────────────────────────────────
echo "=== Updating server zip ==="
mkdir -p /build/existing /build/output
echo "Downloading current build from S3..."
aws s3 cp "s3://${S3_BUCKET}/${BUILD_KEY}" /build/existing.zip --region "${AWS_REGION}"

cd /build/existing
rm -rf ./*
unzip -q /build/existing.zip

NEW_BIN_DIR="\$WORKSPACE/Binaries/Linux"
EXISTING_BIN_DIR=\$(find /build/existing -path "*/Binaries/Linux" -type d | head -1 || echo "")

if [[ -z "\$EXISTING_BIN_DIR" ]]; then
  echo "ERROR: Binaries/Linux not found in extracted zip." >&2
  ls -la /build/existing/
  exit 1
fi

echo "Replacing binaries: \$NEW_BIN_DIR -> \$EXISTING_BIN_DIR"
cp "\$NEW_BIN_DIR/"* "\$EXISTING_BIN_DIR/"
echo "Binaries replaced."

echo "Rezipping..."
cd /build/existing
rm -f /build/output/HyperMageVRServer.zip
zip -r /build/output/HyperMageVRServer.zip .

echo "Uploading to S3..."
aws s3 cp /build/output/HyperMageVRServer.zip \
  "s3://${S3_BUCKET}/builds/latest/HyperMageVRServer.zip" \
  --region "${AWS_REGION}"
echo "ok" | aws s3 cp - "s3://${S3_BUCKET}/builds/latest/compile-success.txt" --region "${AWS_REGION}"

echo "=== Hotpatch complete ==="
aws s3 ls "s3://${S3_BUCKET}/builds/latest/"
ENDSCRIPT

SCRIPT_WIN=$(cygpath -w "$SCRIPT_FILE")
PARAMS_WIN=$(cygpath -w "$PARAMS_FILE")
IS_WARM_VAL="$IS_WARM"
SCRIPT_WIN="$SCRIPT_WIN" PARAMS_WIN="$PARAMS_WIN" IS_WARM_VAL="$IS_WARM_VAL" node -e "
const fs = require('fs');
let script = fs.readFileSync(process.env.SCRIPT_WIN, 'utf8');
// Inject the IS_WARM value so the script can branch correctly
script = script.replace('\${IS_WARM}', process.env.IS_WARM_VAL);
fs.writeFileSync(process.env.PARAMS_WIN, JSON.stringify({commands: [script], executionTimeout: ['5400']}));
"

COMMAND_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "file://$PARAMS_WIN" \
  --timeout-seconds 5400 \
  --comment "HyperMage VR hotpatch" \
  --query 'Command.CommandId' \
  --output text)

rm -f "$SCRIPT_FILE" "$PARAMS_FILE"

echo "SSM command ID: $COMMAND_ID"
if $IS_WARM; then
  echo "Waiting for incremental compile (typically 5-20 min)..."
else
  echo "Waiting for first-run full compile (typically 30-60 min)..."
fi

MAX_WAIT=5400
WAITED=0
INTERVAL=20
STATUS="InProgress"
while [[ "$STATUS" == "InProgress" || "$STATUS" == "Pending" ]]; do
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "ERROR: Timed out after ${MAX_WAIT}s." >&2
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
  echo "  [${WAITED}s] $STATUS"
done

if [[ "$STATUS" != "Success" ]]; then
  echo ""
  echo "Build failed. Fetching output..."
  aws ssm get-command-invocation \
    --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
    --query 'StandardOutputContent' --output text
  aws ssm get-command-invocation \
    --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
    --query 'StandardErrorContent' --output text
  echo ""
  echo "Instance $INSTANCE_ID is still running for inspection."
  echo "  SSM session: aws ssm start-session --target $INSTANCE_ID --region $AWS_REGION"
  echo "  Compile log: aws s3 cp s3://$S3_BUCKET/builds/latest/compile.log - --region $AWS_REGION | tail -100"
  echo "  Stop instance when done: ./scripts/phase4/02c-stop-warm-instance.sh"
  exit 1
fi

echo ""
echo "=== Hotpatch complete in ${WAITED}s ==="
echo "Build: s3://$S3_BUCKET/builds/latest/HyperMageVRServer.zip"
echo ""
echo "Instance $INSTANCE_ID is still running (reuse on next run = incremental compile)."
echo "When done iterating: ./scripts/phase4/02c-stop-warm-instance.sh"
echo "Next step when ready: ./scripts/phase4/03-deploy-gamelift.sh"
