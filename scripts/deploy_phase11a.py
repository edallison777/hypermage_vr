"""
Deploy Phase 11a: WebPlatformAgent Upgrade
==========================================
Steps:
  1. Attach Phase11aWebPlatformPolicy to AgentCore runtime role
     (pre-signed URL generation, audio/asset DynamoDB queries, GM panel uploads)
  2. Redeploy WebPlatform_Agent via launch_bedrock_agentcore

No Terraform needed — all infrastructure already exists from Phase 10.

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase11a.py
"""

import json
import logging
import os
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

REGION       = "eu-west-1"
ACCOUNT      = "732231126129"
REPO_ROOT    = Path(__file__).parent.parent
AGENTS_DIR   = REPO_ROOT / "Agents"
RUNTIME_ROLE = f"arn:aws:iam::{ACCOUNT}:role/AmazonBedrockAgentCoreSDKRuntime-eu-west-1-81c578ca1b"

PHASE11A_POLICY_NAME = "Phase11aWebPlatformPolicy"
PHASE11A_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid":    "WebScenesS3PutGet",
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
            "Sid":    "BuildBucketPresign",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
            ],
            "Resource": [
                f"arn:aws:s3:::hypermage-vr-unreal-build-artifacts-dev/*",
            ],
        },
        {
            "Sid":    "AudioAssetsDynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:GetItem",
                "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-audio-assets-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-audio-assets-dev/index/*",
            ],
        },
        {
            "Sid":    "AssetCatalogueDynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:GetItem",
                "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-asset-catalogue-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-asset-catalogue-dev/index/*",
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


def attach_iam_policy() -> bool:
    print("\n[1/2] Attaching Phase11aWebPlatformPolicy to runtime role...")
    iam       = boto3.client("iam", region_name=REGION)
    role_name = RUNTIME_ROLE.split("/")[-1]
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=PHASE11A_POLICY_NAME,
            PolicyDocument=PHASE11A_POLICY_DOC,
        )
        print(f"  OK — {PHASE11A_POLICY_NAME} attached to {role_name}")
        return True
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return False


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "web-platform" / ".bedrock_agentcore.yaml"
    agent_class = "WebPlatform_Agent"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"\n[2/2] Deploying {agent_class} — starting CodeBuild...")
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


def main():
    print("Phase 11a Deployment — WebPlatformAgent Upgrade")
    print("=" * 60)
    print("New features: audio loading, glTF assets, virtual joystick,")
    print("  tap-to-interact, Cognito gate, PWA manifest, GM panel")
    print("No Terraform needed — reusing Phase 10 infrastructure")

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
        print("\n" + "=" * 60)
        print("ALL STEPS COMPLETE — Phase 11a deployment done")
        print("\nNext: run test_phase11a.py to validate")
        print("  PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase11a.py")
    else:
        print(f"\nFAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
