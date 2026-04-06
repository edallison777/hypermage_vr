#!/usr/bin/env bash
# 02c-stop-warm-instance.sh — Terminate the warm build instance left running by 02c-hotpatch-server.sh.
#
# Run this when you're done iterating and have a good build in S3.
#
# Usage:
#   ./scripts/phase4/02c-stop-warm-instance.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTANCE_FILE="$REPO_ROOT/.warm-build-instance"
AWS_REGION="${AWS_REGION:-eu-west-1}"

if [[ ! -f "$INSTANCE_FILE" ]]; then
  echo "No warm instance file found ($INSTANCE_FILE). Nothing to stop."
  exit 0
fi

INSTANCE_ID=$(cat "$INSTANCE_FILE" | tr -d '[:space:]')
echo "Warm instance: $INSTANCE_ID"

STATE=$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text 2>/dev/null || echo "not-found")

echo "State: $STATE"

if [[ "$STATE" == "running" || "$STATE" == "stopping" || "$STATE" == "pending" ]]; then
  echo "Terminating $INSTANCE_ID..."
  aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  echo "Waiting for termination..."
  aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  echo "Terminated."
else
  echo "Instance is already '$STATE' — no action needed."
fi

rm -f "$INSTANCE_FILE"
echo "Cleaned up $INSTANCE_FILE."
