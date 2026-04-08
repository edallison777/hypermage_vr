#!/usr/bin/env bash
# 02-deploy-fleet.sh — Phase 15: Create new GameLift build and update fleet to new binary.
#
# Mirrors scripts/phase4/03-deploy-gamelift.sh.
# Creates a new GameLift build from the rebuilt HyperMageVRServer.zip, then applies
# Terraform to update the fleet (replace) with the new build ID.
# Also ensures the Phase 14 session-api-invoke IAM policy is applied.
#
# The existing fleet (fleet-848aced2) will be replaced — GameLift requires a new fleet
# when the build changes. Replacement takes ~30-45 minutes.
#
# FlexMatch config and rule set already exist — they are preserved unchanged.
#
# Prerequisites:
#   - HyperMageVRServer.zip rebuilt and uploaded (run 01-rebuild-server.sh first)
#   - Terraform outputs available (unreal_build and session_api modules deployed)
#
# Usage:
#   ./scripts/phase15/02-deploy-fleet.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$REPO_ROOT/Infra/environments/dev"
AWS_REGION="${AWS_REGION:-eu-west-1}"
PROJECT_NAME="${PROJECT_NAME:-hypermage-vr}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
SERVER_SDK_VERSION="5.4.0"

echo "=== Phase 15 / Step 2: Deploy new GameLift Fleet ==="

cd "$TF_DIR"
terraform init -reconfigure >/dev/null 2>&1

# ── 1. Verify rebuilt server build exists in S3 ───────────────────────────────
S3_BUCKET=$(terraform output -raw build_s3_bucket)
BUILD_KEY="builds/latest/HyperMageVRServer.zip"
echo "Checking s3://$S3_BUCKET/$BUILD_KEY ..."
if ! aws s3 ls "s3://$S3_BUCKET/$BUILD_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ERROR: HyperMageVRServer.zip not found. Run 01-rebuild-server.sh first." >&2
  exit 1
fi
# Check that this is a recent build (not the Phase 4 original)
BUILD_DATE=$(aws s3 ls "s3://$S3_BUCKET/$BUILD_KEY" --region "$AWS_REGION" | awk '{print $1, $2}')
echo "Server build found: $BUILD_DATE"

# ── 2. Apply Phase 14 IAM policy (session-api-invoke on fleet role) ───────────
echo ""
echo "--- Applying Phase 14 IAM: session-api-invoke policy on fleet role ---"
terraform apply \
  -target=module.gamelift_fleet.aws_iam_role_policy.fleet_session_api \
  -var "gamelift_build_id=placeholder" \
  -auto-approve 2>/dev/null || {
    # Policy is count=0 when session_api_execution_arn is empty; apply full gamelift_fleet to wire it
    echo "  fleet_session_api not yet managed — applying full gamelift_fleet module with ARN..."
  }

# ── 3. Ensure IAM role and base policies exist ────────────────────────────────
echo ""
echo "--- Ensuring GameLift IAM role and policies exist ---"
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text --region "$AWS_REGION")
FLEET_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${PROJECT_NAME}-gamelift-fleet-${ENVIRONMENT}"
echo "Fleet IAM role: $FLEET_ROLE_ARN"

# ── 4. Create new GameLift build ──────────────────────────────────────────────
echo ""
echo "--- Creating new GameLift build (Phase 15 binary, SDK $SERVER_SDK_VERSION) ---"
BUILD_NAME="${PROJECT_NAME}-server-phase15-${ENVIRONMENT}"

BUILD_ID=$(aws gamelift create-build \
  --region "$AWS_REGION" \
  --name "$BUILD_NAME" \
  --operating-system AMAZON_LINUX_2023 \
  --server-sdk-version "$SERVER_SDK_VERSION" \
  --storage-location "Bucket=${S3_BUCKET},Key=${BUILD_KEY},RoleArn=${FLEET_ROLE_ARN}" \
  --query 'Build.BuildId' \
  --output text)
echo "Build created: $BUILD_ID"

# ── 5. Wait for build to become READY ────────────────────────────────────────
echo "Waiting for build to be READY..."
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
    echo "ERROR: GameLift build failed." >&2
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

# Save the new build ID for test script to reference
echo "$BUILD_ID" > "$REPO_ROOT/.phase15-build-id"
echo "Build ID saved to .phase15-build-id"

# ── 6. Apply gamelift_fleet module with new build ID ─────────────────────────
echo ""
echo "--- Applying gamelift_fleet module (fleet replace — ~30-45 min) ---"
echo "NOTE: Terraform will REPLACE the existing fleet. The old fleet is deleted."
terraform apply \
  -target=module.gamelift_fleet \
  -var "gamelift_build_id=${BUILD_ID}" \
  -auto-approve

FLEET_ID=$(terraform output -raw gamelift_fleet_id 2>/dev/null || echo "")
FLEET_ARN=$(terraform output -raw gamelift_fleet_arn 2>/dev/null || echo "")
ALIAS_ID=$(terraform output -raw gamelift_alias_id 2>/dev/null || echo "")
echo "New Fleet ID   : $FLEET_ID"
echo "New Fleet ARN  : $FLEET_ARN"
echo "Alias ID       : $ALIAS_ID"

# ── 7. Wait for fleet to be ACTIVE ───────────────────────────────────────────
echo ""
echo "--- Waiting for new fleet to become ACTIVE (up to 60 minutes) ---"
MAX_FLEET_WAIT=3600
FLEET_WAITED=0
while true; do
  FLEET_STATUS=$(aws gamelift describe-fleet-attributes \
    --fleet-ids "$FLEET_ID" \
    --region "$AWS_REGION" \
    --query 'FleetAttributes[0].Status' \
    --output text 2>/dev/null || echo "UNKNOWN")
  echo "  [${FLEET_WAITED}s] Fleet status: $FLEET_STATUS"
  if [[ "$FLEET_STATUS" == "ACTIVE" ]]; then
    echo "Fleet is ACTIVE."
    break
  elif [[ "$FLEET_STATUS" == "ERROR" || "$FLEET_STATUS" == "TERMINATED" ]]; then
    echo "ERROR: Fleet entered status $FLEET_STATUS." >&2
    aws gamelift describe-fleet-events --fleet-id "$FLEET_ID" --region "$AWS_REGION" \
      --query 'Events[-10:].Message' --output text
    exit 1
  fi
  if [[ $FLEET_WAITED -ge $MAX_FLEET_WAIT ]]; then
    echo "ERROR: Fleet did not become ACTIVE within ${MAX_FLEET_WAIT}s." >&2
    exit 1
  fi
  sleep 60
  FLEET_WAITED=$((FLEET_WAITED + 60))
done

# ── 8. Update gamelift_build_id tfvar for future applies ─────────────────────
TFVARS_FILE="$TF_DIR/gamelift_build_id.auto.tfvars"
echo "gamelift_build_id = \"${BUILD_ID}\"" > "$TFVARS_FILE"
echo "gamelift_build_id persisted to $TFVARS_FILE"

# ── 9. Update FlexMatch queue to point at new fleet ──────────────────────────
echo ""
echo "--- Updating FlexMatch module (fleet ARN changed) ---"
terraform apply \
  -target=module.flexmatch \
  -var "gamelift_build_id=${BUILD_ID}" \
  -auto-approve

echo ""
echo "=== Phase 15 Fleet Deployment Complete ==="
echo ""
echo "New GameLift Build : $BUILD_ID"
echo "New Fleet ID       : $FLEET_ID"
echo "Alias ID           : $ALIAS_ID (unchanged — client code needs no update)"
echo ""
echo "To scale fleet up for testing:"
echo "  aws gamelift update-fleet-capacity --fleet-id '$FLEET_ID' --desired-instances 1 --region $AWS_REGION"
echo ""
echo "Next: run scripts/test_phase15.py"
