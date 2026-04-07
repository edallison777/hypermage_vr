"""
Deploy Phase 10: Web Platform Foundation
=========================================
Steps:
  1. Terraform apply (web-platform module) — S3 + CloudFront + DynamoDB + WebSocket API
  2. Attach Phase10WebPlatformPolicy to the AgentCore runtime role
  3. Deploy WebPlatformAgent to AgentCore

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase10.py

Cost profile:
  S3 + CloudFront — zero idle cost (pay per request)
  DynamoDB (PAY_PER_REQUEST) — zero idle cost
  API GW WebSocket — zero idle cost
  CloudFront — no charge until scenes are accessed
  GameLift fleet stays at DESIRED=0 (unchanged).
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONIOENCODING"] = "utf-8"

logging.disable(logging.CRITICAL)

import boto3
from rich.console import Console
from bedrock_agentcore_starter_toolkit.operations.runtime import launch_bedrock_agentcore

REGION        = "eu-west-1"
ACCOUNT       = "732231126129"
REPO_ROOT     = Path(__file__).parent.parent
AGENTS_DIR    = REPO_ROOT / "Agents"
TERRAFORM_DIR = REPO_ROOT / "Infra" / "environments" / "dev"
RUNTIME_ROLE  = f"arn:aws:iam::{ACCOUNT}:role/AmazonBedrockAgentCoreSDKRuntime-eu-west-1-81c578ca1b"

PHASE10_POLICY_NAME = "Phase10WebPlatformPolicy"
PHASE10_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid":    "WebScenesS3",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:HeadObject",
                "s3:ListBucket",
            ],
            "Resource": [
                f"arn:aws:s3:::hypermage-vr-web-scenes-dev",
                f"arn:aws:s3:::hypermage-vr-web-scenes-dev/*",
            ],
        },
        {
            "Sid":    "WebScenesDynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-web-scenes-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-web-scenes-dev/index/*",
            ],
        },
        {
            "Sid":    "CloudFrontInvalidate",
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateInvalidation",
                "cloudfront:ListDistributions",
                "cloudfront:GetDistribution",
            ],
            "Resource": "*",
        },
        {
            "Sid":    "WebPlatformSSM",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": [
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/cloudfront-domain",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/ws-url",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/scenes-bucket",
            ],
        },
    ],
})


def run_terraform() -> bool:
    print("\n[1/3] Terraform apply (web-platform module)...")
    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-target=module.web_platform"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  FAILED:\n{result.stderr[-3000:]}")
            return False
        # Extract key outputs
        for line in result.stdout.split("\n"):
            if "cloudfront" in line.lower() or "ws_url" in line.lower() or "bucket" in line.lower():
                print(f"  {line.strip()}")
        print("  OK — S3 + CloudFront + DynamoDB + WebSocket API created")
        return True
    except FileNotFoundError:
        print("  SKIP — terraform not in PATH, run manually:")
        print(f"    cd {TERRAFORM_DIR}")
        print("    terraform apply -auto-approve -target=module.web_platform")
        return True
    except subprocess.TimeoutExpired:
        print("  TIMEOUT — CloudFront distributions can take 5-10 min to deploy.")
        print("  Re-run deploy_phase10.py to resume — Terraform is idempotent.")
        return False


def attach_iam_policy() -> bool:
    print("\n[2/3] Attaching Phase10WebPlatformPolicy to runtime role...")
    iam       = boto3.client("iam", region_name=REGION)
    role_name = RUNTIME_ROLE.split("/")[-1]
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=PHASE10_POLICY_NAME,
            PolicyDocument=PHASE10_POLICY_DOC,
        )
        print(f"  OK — {PHASE10_POLICY_NAME} attached to {role_name}")
        return True
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return False


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "web-platform" / ".bedrock_agentcore.yaml"
    agent_class = "WebPlatform_Agent"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"\n[3/3] Deploying {agent_class} — starting CodeBuild...")
    try:
        result    = launch_bedrock_agentcore(
            config_path=config_path,
            agent_name=agent_class,
            local=False,
            use_codebuild=True,
            auto_update_on_conflict=True,
            console=console,
        )
        agent_id  = result.agent_id
        agent_arn = f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/{agent_id}"
        print(f"  SUCCESS — {agent_class}: {agent_id}")
        return {"agent": agent_class, "agent_id": agent_id, "agent_arn": agent_arn, "status": "deployed"}
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return {"agent": agent_class, "status": "failed", "error": str(exc)}


def print_terraform_outputs() -> None:
    """Print the key outputs after deployment."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            cf = outputs.get("web_platform_cloudfront_domain", {}).get("value", "")
            ws = outputs.get("web_platform_ws_url", {}).get("value", "")
            bucket = outputs.get("web_platform_bucket", {}).get("value", "")
            if cf:
                print(f"\n  CloudFront: https://{cf}")
            if ws:
                print(f"  WebSocket:  {ws}")
            if bucket:
                print(f"  S3 bucket:  {bucket}")
    except Exception:
        pass


def main():
    print("Phase 10 Deployment — Web Platform Foundation")
    print("=" * 60)
    print("Cost-safe: serverless only — S3/CloudFront/DynamoDB/API GW WebSocket")
    print("GameLift fleet: stays at DESIRED=0")

    if not run_terraform():
        sys.exit(1)
    if not attach_iam_policy():
        sys.exit(1)

    result = deploy_agent()

    results_path = AGENTS_DIR / "deployment_results.json"
    try:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

    if result["status"] == "deployed":
        existing = [e for e in existing if e.get("agent") != result["agent"]]
        existing.append({
            "agent":     result["agent"],
            "agent_id":  result["agent_id"],
            "agent_arn": result["agent_arn"],
            "status":    "READY",
        })
        results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print_terraform_outputs()

    print("\n" + "=" * 60)
    if result["status"] == "deployed":
        print("ALL STEPS COMPLETE — Phase 10 deployment done")
        print("\nNext: run test_phase10.py to validate")
        print("  PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase10.py")
    else:
        print(f"FAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
