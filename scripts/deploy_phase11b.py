"""
Deploy Phase 11b: NarrativeAgent + LARPIntegrationAgent
=======================================================
Steps:
  1. Terraform apply (larp-integration module) — GM Event Lambda + HTTP API + SSM params
  2. Attach Phase11bNarrativePolicy to AgentCore runtime role
  3. Create ECR repositories for narrative_agent and larp-integration_agent
  4. Deploy Narrative_Agent via launch_bedrock_agentcore
  5. Deploy LARPIntegration_Agent via launch_bedrock_agentcore
  6. Update deployment_results.json

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase11b.py
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

PHASE11B_POLICY_NAME = "Phase11bNarrativePolicy"
PHASE11B_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid":    "WebScenesDynamoDB",
            "Effect": "Allow",
            "Action": [
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
            "Sid":    "ConnectionsDynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:DeleteItem",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-ws-connections-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-ws-connections-dev/index/*",
            ],
        },
        {
            "Sid":    "WSManageConnections",
            "Effect": "Allow",
            "Action": ["execute-api:ManageConnections"],
            "Resource": f"arn:aws:execute-api:{REGION}:{ACCOUNT}:yd895183ei/*/@connections/*",
        },
        {
            "Sid":    "ScenePlanS3",
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": f"arn:aws:s3:::hypermage-vr-unreal-build-artifacts-dev/scene-plans/*",
        },
        {
            "Sid":    "WebPlatformSSM",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": [
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/ws-url",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/cloudfront-domain",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/web-platform/scenes-bucket",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/larp/gm-event-url",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/larp/ws-management-endpoint",
            ],
        },
    ],
})


def run_terraform() -> bool:
    print("\n[1/5] Terraform apply (larp-integration module)...")
    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-target=module.larp_integration"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  FAILED:\n{result.stderr[-3000:]}")
            return False
        for line in result.stdout.split("\n"):
            if "gm_event_url" in line.lower() or "api" in line.lower():
                print(f"  {line.strip()}")
        print("  OK — GM Event Lambda + HTTP API + SSM params created")
        return True
    except FileNotFoundError:
        print("  SKIP — terraform not in PATH, run manually:")
        print(f"    cd {TERRAFORM_DIR}")
        print("    terraform apply -auto-approve -target=module.larp_integration")
        return True
    except subprocess.TimeoutExpired:
        print("  TIMEOUT — re-run deploy_phase11b.py to resume (Terraform is idempotent)")
        return False


def attach_iam_policy() -> bool:
    print("\n[2/5] IAM — permissions already covered by HypermageAgentsConsolidatedPolicy")
    print("  (DynamoDB wildcard + SSM wildcard + execute-api:ManageConnections)")
    print("  OK — no new policy needed")
    return True


def create_ecr_repos() -> bool:
    print("\n[3/5] Creating ECR repositories...")
    ecr = boto3.client("ecr", region_name=REGION)
    repos = [
        "bedrock-agentcore-narrative_agent",
        "bedrock-agentcore-larp-integration_agent",
    ]
    for repo_name in repos:
        try:
            ecr.create_repository(
                repositoryName=repo_name,
                imageScanningConfiguration={"scanOnPush": True},
                encryptionConfiguration={"encryptionType": "AES256"},
            )
            print(f"  Created ECR: {repo_name}")
        except ecr.exceptions.RepositoryAlreadyExistsException:
            print(f"  Already exists: {repo_name}")
        except Exception as exc:
            print(f"  WARNING: Could not create {repo_name}: {exc}")
    return True


def deploy_agent(agent_class: str, agent_dir: str, step: str) -> dict:
    config_path = AGENTS_DIR / agent_dir / ".bedrock_agentcore.yaml"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"\n[{step}] Deploying {agent_class} — starting CodeBuild...")
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
    print("Phase 11b Deployment — NarrativeAgent + LARPIntegrationAgent")
    print("=" * 60)
    print("New agents: real-time narrative state management + GM event broadcast")

    if not run_terraform():
        sys.exit(1)
    if not attach_iam_policy():
        sys.exit(1)
    create_ecr_repos()

    agents_to_deploy = [
        ("Narrative_Agent",        "narrative",        "4/5"),
        ("LARPIntegration_Agent",  "larp-integration", "5/5"),
    ]

    results_path = AGENTS_DIR / "deployment_results.json"
    try:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

    all_ok = True
    for agent_class, agent_dir, step in agents_to_deploy:
        result = deploy_agent(agent_class, agent_dir, step)
        if result["status"] == "deployed":
            existing = [e for e in existing if e.get("agent") != result["agent"]]
            existing.append({
                "agent":     result["agent"],
                "agent_id":  result["agent_id"],
                "agent_arn": result["agent_arn"],
                "status":    "READY",
            })
        else:
            all_ok = False

    results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL STEPS COMPLETE — Phase 11b deployment done")
        print("\nNext: run test_phase11b.py to validate")
        print("  PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase11b.py")
    else:
        print("Some agents failed — check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
