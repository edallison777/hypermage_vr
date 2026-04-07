"""
Deploy Phase 7: Asset Ingestion Pipeline
=========================================
Steps:
  1. Apply Terraform (asset-pipeline module) — creates DynamoDB, Lambda functions, ECS cluster
  2. Attach Phase7AssetPipelinePolicy to the AgentCore runtime role
  3. Redeploy AssetPipelineAgent (with real DynamoDB tools)
  4. Redeploy EnvironmentDesigner (with get_available_assets() tool)

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase7.py

Cost safety: All Phase 7 resources are serverless/on-demand (Lambda, DynamoDB on-demand,
ECS Fargate task-per-use). GameLift fleet stays at DESIRED=0.
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

PHASE7_AGENTS = [
    {"dir_name": "asset-pipeline",              "agent_class_name": "AssetPipeline"},
    {"dir_name": "conversation-level-designer", "agent_class_name": "ConversationLevelDesigner"},
]


# ── Step 1: Terraform ─────────────────────────────────────────────────────────

def run_terraform() -> bool:
    print("\n[1/4] Terraform apply (asset-pipeline module)...")
    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-target=module.asset_pipeline"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  FAILED:\n{result.stderr[-2000:]}")
            return False
        print("  OK — asset-pipeline resources applied")
        return True
    except FileNotFoundError:
        print("  SKIP — terraform not in PATH, run manually:")
        print(f"    cd {TERRAFORM_DIR}")
        print("    terraform apply -auto-approve -target=module.asset_pipeline")
        return True  # non-fatal — agent deployments can proceed


# ── Step 2: IAM policy ────────────────────────────────────────────────────────

PHASE7_POLICY_NAME = "Phase7AssetPipelinePolicy"
PHASE7_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AssetCatalogueAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                "dynamodb:Query", "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-asset-catalogue-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-asset-catalogue-dev/index/*",
            ],
        },
        {
            "Sid": "AssetS3Access",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:HeadObject", "s3:ListBucket"],
            "Resource": [
                "arn:aws:s3:::hypermage-vr-unreal-build-artifacts-dev",
                "arn:aws:s3:::hypermage-vr-unreal-build-artifacts-dev/*",
            ],
        },
    ],
})


def attach_iam_policy() -> bool:
    print("\n[2/4] Attaching Phase7AssetPipelinePolicy to runtime role...")
    iam       = boto3.client("iam", region_name=REGION)
    role_name = RUNTIME_ROLE.split("/")[-1]
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=PHASE7_POLICY_NAME,
            PolicyDocument=PHASE7_POLICY_DOC,
        )
        print(f"  OK — {PHASE7_POLICY_NAME} attached to {role_name}")
        return True
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return False


# ── Step 3 & 4: Deploy agents ─────────────────────────────────────────────────

def deploy_agent(agent: dict) -> dict:
    config_path = AGENTS_DIR / agent["dir_name"] / ".bedrock_agentcore.yaml"
    agent_class = f"{agent['agent_class_name']}_Agent"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"  [deploy] {agent_class} — starting CodeBuild...")
    try:
        result = launch_bedrock_agentcore(
            config_path=config_path,
            agent_name=agent_class,
            local=False,
            use_codebuild=True,
            auto_update_on_conflict=True,
            console=console,
        )
        agent_id  = result.agent_id
        agent_arn = f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/{agent_id}"
        print(f"  [deploy] {agent_class} — SUCCESS  agent_id={agent_id}")
        return {"agent": agent_class, "agent_id": agent_id, "agent_arn": agent_arn, "status": "deployed"}
    except Exception as exc:
        print(f"  [deploy] {agent_class} — FAILED: {exc}")
        return {"agent": agent_class, "agent_id": None, "status": "failed", "error": str(exc)}


def main():
    print("Phase 7 Deployment — Asset Ingestion Pipeline")
    print("=" * 60)
    print("Cost-safe: Lambda + DynamoDB on-demand + ECS Fargate (task-per-use)")
    print("GameLift fleet: stays at DESIRED=0")

    if not run_terraform():
        sys.exit(1)
    if not attach_iam_policy():
        sys.exit(1)

    print("\n[3/4] Deploying AssetPipelineAgent...")
    print("[4/4] Deploying EnvironmentDesigner (ConversationLevelDesigner)...")
    results = []
    for agent in PHASE7_AGENTS:
        r = deploy_agent(agent)
        results.append(r)
        print()

    # Update deployment_results.json
    results_path = AGENTS_DIR / "deployment_results.json"
    try:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

    deployed = [r for r in results if r["status"] == "deployed"]
    failed   = [r for r in results if r["status"] == "failed"]

    for new in deployed:
        existing = [e for e in existing if e.get("agent") != new["agent"]]
        existing.append({"agent": new["agent"], "agent_id": new["agent_id"],
                         "agent_arn": new["agent_arn"], "status": "READY"})
    results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print("=" * 60)
    print(f"Deployed: {len(deployed)}/{len(results)}")
    if failed:
        print(f"Failed:   {[r['agent'] for r in failed]}")
        sys.exit(1)
    else:
        print("ALL STEPS COMPLETE — Phase 7 deployment done")
        print("\nNext: run test_phase7.py to validate end-to-end")


if __name__ == "__main__":
    main()
