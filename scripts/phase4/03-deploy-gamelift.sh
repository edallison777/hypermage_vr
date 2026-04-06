#!/usr/bin/env bash
# 03-deploy-gamelift.sh — Create GameLift build (via CLI), then apply fleet + FlexMatch.
#
# The Terraform AWS provider does not support the server_sdk_version argument on
# aws_gamelift_build, which is required for AMAZON_LINUX_2023 fleets (SDK >= 5.0).
# So this script creates the build directly via the AWS CLI (which does support it),
# then passes the resulting build ID to Terraform as a variable.
#
# Prerequisites:
#   - HyperMageVRServer.zip uploaded to S3 (run 02-compile-server.sh first)
#   - Terraform >= 1.5 and AWS CLI configured
#   - The gamelift_fleet IAM role must exist (created on first Terraform apply)
#
# Usage:
#   ./scripts/phase4/03-deploy-gamelift.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"
PROJECT_NAME="${PROJECT_NAME:-hypermage-vr}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
SERVER_SDK_VERSION="5.4.0"

echo "=== Phase 4 / Step 3: Deploy GameLift Fleet + FlexMatch ==="

cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1

# ── 1. Verify server build exists in S3 ───────────────────────────────────────
S3_BUCKET=$(terraform output -raw build_s3_bucket 2>/dev/null || true)
if [[ -z "$S3_BUCKET" ]]; then
  echo "ERROR: unreal_build outputs not available. Run 02-compile-server.sh first." >&2
  exit 1
fi

BUILD_KEY="builds/latest/HyperMageVRServer.zip"
echo "Checking s3://$S3_BUCKET/$BUILD_KEY ..."
if ! aws s3 ls "s3://$S3_BUCKET/$BUILD_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ERROR: Server build not found in S3. Run 02-compile-server.sh first." >&2
  exit 1
fi
echo "Server build found."

# ── 2. Ensure IAM role exists (needed for create-build storage-location) ──────
# The role is created by the gamelift_fleet module. Apply just IAM resources first
# so the role exists even on a fresh deploy before we call create-build.
echo ""
echo "--- Ensuring GameLift IAM role exists ---"
terraform apply \
  -target=module.gamelift_fleet.aws_iam_role.fleet \
  -target=module.gamelift_fleet.aws_iam_role_policy.fleet_logs \
  -target=module.gamelift_fleet.aws_iam_role_policy.fleet_s3 \
  -var "gamelift_build_id=placeholder" \
  -auto-approve

ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text --region "$AWS_REGION")
FLEET_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${PROJECT_NAME}-gamelift-fleet-${ENVIRONMENT}"
echo "Fleet IAM role: $FLEET_ROLE_ARN"

# ── 3. Create GameLift build via CLI (supports --server-sdk-version) ──────────
echo ""
echo "--- Creating GameLift build (SDK $SERVER_SDK_VERSION, AMAZON_LINUX_2023) ---"
BUILD_NAME="${PROJECT_NAME}-server-${ENVIRONMENT}"

BUILD_ID=$(aws gamelift create-build \
  --region "$AWS_REGION" \
  --name "$BUILD_NAME" \
  --operating-system AMAZON_LINUX_2023 \
  --server-sdk-version "$SERVER_SDK_VERSION" \
  --storage-location "Bucket=${S3_BUCKET},Key=${BUILD_KEY},RoleArn=${FLEET_ROLE_ARN}" \
  --query 'Build.BuildId' \
  --output text)
echo "Build created: $BUILD_ID"

# ── 4. Wait for build to become READY ─────────────────────────────────────────
echo "Waiting for build to be READY (GameLift ingests the zip from S3)..."
MAX_WAIT=600
WAITED=0
while true; do
  STATUS=$(aws gamelift describe-build \
    --build-id "$BUILD_ID" \
    --region "$AWS_REGION" \
    --query 'Build.Status' \
    --output text)
  echo "  [${WAITED}s] Build status: $STATUS"
  if [[ "$STATUS" == "READY" ]]; then
    echo "Build is READY."
    break
  elif [[ "$STATUS" == "FAILED" ]]; then
    echo "ERROR: Build failed." >&2
    aws gamelift describe-build --build-id "$BUILD_ID" --region "$AWS_REGION"
    exit 1
  fi
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "ERROR: Build did not become READY within ${MAX_WAIT}s." >&2
    exit 1
  fi
  sleep 15
  WAITED=$((WAITED + 15))
done

# ── 5. Apply GameLift fleet (passing build ID as variable) ────────────────────
echo ""
echo "--- Applying gamelift_fleet module ---"
terraform apply \
  -target=module.gamelift_fleet \
  -var "gamelift_build_id=${BUILD_ID}" \
  -auto-approve

FLEET_ID=$(terraform output -raw gamelift_fleet_id 2>/dev/null || echo "")
FLEET_ARN=$(terraform output -raw gamelift_fleet_arn 2>/dev/null || echo "")
ALIAS_ID=$(terraform output -raw gamelift_alias_id 2>/dev/null || echo "")
echo "Fleet ID   : $FLEET_ID"
echo "Fleet ARN  : $FLEET_ARN"
echo "Alias ID   : $ALIAS_ID"

# ── 6. Apply FlexMatch ────────────────────────────────────────────────────────
echo ""
echo "--- Applying flexmatch module ---"
terraform apply \
  -target=module.flexmatch \
  -var "gamelift_build_id=${BUILD_ID}" \
  -auto-approve

MATCHMAKING_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
RULE_SET_NAME="${PROJECT_NAME}-${ENVIRONMENT}-rules"
QUEUE_ARN=$(terraform output -raw game_session_queue_arn 2>/dev/null || echo "")
FLEXMATCH_RULE_SET_FILE="$REPO_ROOT/Infra/modules/flexmatch/generated/rule-set-${ENVIRONMENT}.json"
FLEXMATCH_CONFIG_FILE="$REPO_ROOT/Infra/modules/flexmatch/generated/matchmaking-config-${ENVIRONMENT}.json"

# ── 7. Deploy FlexMatch rule set via CLI ──────────────────────────────────────
echo ""
echo "--- Deploying FlexMatch rule set ---"
EXISTING_RULE_SET=$(aws gamelift describe-matchmaking-rule-sets \
  --rule-set-names "$RULE_SET_NAME" \
  --region "$AWS_REGION" \
  --query 'RuleSets[0].RuleSetName' \
  --output text 2>/dev/null || echo "")

if [[ "$EXISTING_RULE_SET" == "$RULE_SET_NAME" ]]; then
  echo "Rule set '$RULE_SET_NAME' already exists — skipping."
else
  RULE_SET_BODY=$(cat "$FLEXMATCH_RULE_SET_FILE")
  aws gamelift create-matchmaking-rule-set \
    --name "$RULE_SET_NAME" \
    --rule-set-body "$RULE_SET_BODY" \
    --region "$AWS_REGION"
  echo "Rule set created: $RULE_SET_NAME"
fi

# ── 8. Deploy FlexMatch matchmaking configuration via CLI ─────────────────────
echo ""
echo "--- Deploying FlexMatch matchmaking configuration ---"
EXISTING_CONFIG=$(aws gamelift describe-matchmaking-configurations \
  --names "$MATCHMAKING_NAME" \
  --region "$AWS_REGION" \
  --query 'Configurations[0].Name' \
  --output text 2>/dev/null || echo "")

if [[ "$EXISTING_CONFIG" == "$MATCHMAKING_NAME" ]]; then
  echo "Matchmaking config '$MATCHMAKING_NAME' already exists — skipping."
else
  # The JSON file uses PascalCase keys as required by the CLI --cli-input-json format
  MATCHMAKING_CONFIG_WIN=$(cygpath -w "$FLEXMATCH_CONFIG_FILE" 2>/dev/null || echo "$FLEXMATCH_CONFIG_FILE")
  aws gamelift create-matchmaking-configuration \
    --cli-input-json "file://$MATCHMAKING_CONFIG_WIN" \
    --region "$AWS_REGION"
  echo "Matchmaking configuration created: $MATCHMAKING_NAME"
fi

echo "Matchmaking config : $MATCHMAKING_NAME"
echo "Session queue ARN  : $QUEUE_ARN"

# ── 9. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "=== Phase 4 Complete ==="
echo ""
echo "Resources live in $AWS_REGION:"
echo "  GameLift Build : $BUILD_ID"
echo "  GameLift Fleet : $FLEET_ID ($ALIAS_ID)"
echo "  FlexMatch      : $MATCHMAKING_NAME"
echo "  Session Queue  : $QUEUE_ARN"
echo ""
echo "Verify fleet is active:"
echo "  aws gamelift describe-fleet-attributes --fleet-ids '$FLEET_ID' --region $AWS_REGION"
echo "  aws gamelift describe-fleet-capacity --fleet-ids '$FLEET_ID' --region $AWS_REGION"
echo ""
echo "Lambda MATCHMAKING_CONFIG_NAME should be: $MATCHMAKING_NAME"
echo "(Update Infra/modules/session-api if it differs.)"
