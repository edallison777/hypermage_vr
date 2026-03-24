#!/usr/bin/env bash
# 03-deploy-gamelift.sh — Apply gamelift_fleet and flexmatch Terraform modules.
# Verifies the server build zip exists in S3 first.
#
# Prerequisites:
#   - HyperMageVRServer.zip uploaded to S3 (run 02-compile-server.sh first)
#   - Terraform >= 1.5 and AWS CLI configured
#
# Usage:
#   ./scripts/phase4/03-deploy-gamelift.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"

echo "=== Phase 4 / Step 3: Deploy GameLift Fleet + FlexMatch ==="

# ── 1. Verify server build exists ─────────────────────────────────────────────
cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1
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

# ── 2. Apply GameLift fleet ────────────────────────────────────────────────────
echo ""
echo "--- Applying gamelift_fleet module ---"
terraform apply \
  -target=module.gamelift_fleet \
  -auto-approve

FLEET_ID=$(terraform output -raw gamelift_fleet_id)
FLEET_ARN=$(terraform output -raw gamelift_fleet_arn)
ALIAS_ID=$(terraform output -raw gamelift_alias_id)
echo "Fleet ID   : $FLEET_ID"
echo "Fleet ARN  : $FLEET_ARN"
echo "Alias ID   : $ALIAS_ID"

# ── 3. Apply FlexMatch ────────────────────────────────────────────────────────
echo ""
echo "--- Applying flexmatch module ---"
terraform apply \
  -target=module.flexmatch \
  -auto-approve

MATCHMAKING_NAME=$(terraform output -raw matchmaking_configuration_name)
QUEUE_ARN=$(terraform output -raw game_session_queue_arn)
echo "Matchmaking config : $MATCHMAKING_NAME"
echo "Session queue ARN  : $QUEUE_ARN"

# ── 4. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "=== Phase 4 Complete ==="
echo ""
echo "Resources live in $AWS_REGION:"
echo "  GameLift Fleet : $FLEET_ID ($ALIAS_ID)"
echo "  FlexMatch      : $MATCHMAKING_NAME"
echo "  Session Queue  : $QUEUE_ARN"
echo ""
echo "Verify matchmaking is working:"
echo "  aws gamelift describe-matchmaking-configurations --names '$MATCHMAKING_NAME' --region $AWS_REGION"
echo "  aws gamelift describe-fleet-capacity --fleet-ids '$FLEET_ID' --region $AWS_REGION"
echo ""
echo "Lambda MATCHMAKING_CONFIG_NAME should be: $MATCHMAKING_NAME"
echo "(Update Infra/modules/session-api if it differs.)"
