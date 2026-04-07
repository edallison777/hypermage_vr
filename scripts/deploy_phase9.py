"""
Deploy Phase 9: UnrealMCP Bridge
==================================
Steps:
  1. Terraform apply (unreal-bridge module) — creates SSM placeholder
  2. Attach Phase9UnrealBridgePolicy to the AgentCore runtime role
  3. Redeploy UnrealLevelBuilderAgent (with real HTTP-backed bridge tools)

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase9.py

Cost safety: No cloud compute. Bridge runs on dev PC. Zero idle cost.
GameLift fleet stays at DESIRED=0.

To activate live UE5 editor control after deployment:
  1. Open UE5 with Remote Control plugin enabled
  2. Run: bash scripts/unreal-bridge/start.sh --ngrok
     (auto-updates SSM with ngrok URL)
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

PHASE9_POLICY_NAME = "Phase9UnrealBridgePolicy"
PHASE9_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Sid":    "UnrealBridgeSSM",
        "Effect": "Allow",
        "Action": ["ssm:GetParameter"],
        "Resource": [
            f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/unreal-bridge-url",
        ],
    }],
})


def run_terraform() -> bool:
    print("\n[1/3] Terraform apply (unreal-bridge module)...")
    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-target=module.unreal_bridge"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"  FAILED:\n{result.stderr[-2000:]}")
            return False
        print("  OK — unreal-bridge SSM parameter created")
        return True
    except FileNotFoundError:
        print("  SKIP — terraform not in PATH, run manually:")
        print(f"    cd {TERRAFORM_DIR}")
        print("    terraform apply -auto-approve -target=module.unreal_bridge")
        return True


def attach_iam_policy() -> bool:
    print("\n[2/3] Attaching Phase9UnrealBridgePolicy to runtime role...")
    iam       = boto3.client("iam", region_name=REGION)
    role_name = RUNTIME_ROLE.split("/")[-1]
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=PHASE9_POLICY_NAME,
            PolicyDocument=PHASE9_POLICY_DOC,
        )
        print(f"  OK — {PHASE9_POLICY_NAME} attached to {role_name}")
        return True
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return False


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "unreal-level-builder" / ".bedrock_agentcore.yaml"
    agent_class = "UnrealLevelBuilder_Agent"
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


def main():
    print("Phase 9 Deployment — UnrealMCP Bridge")
    print("=" * 60)
    print("Cost-safe: no cloud compute — bridge runs on dev PC only.")
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
            "agent": result["agent"], "agent_id": result["agent_id"],
            "agent_arn": result["agent_arn"], "status": "READY",
        })
        results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    if result["status"] == "deployed":
        print("ALL STEPS COMPLETE — Phase 9 deployment done")
        print("\nTo activate live UE5 editor control:")
        print("  1. Open UE5, enable Remote Control plugin")
        print("  2. Add to Config/DefaultEngine.ini:")
        print("       [/Script/RemoteControl.RemoteControlSettings]")
        print("       bIsRemoteControlHttpServerEnabled=True")
        print("       RemoteControlHttpServerPort=30010")
        print("  3. Run: bash scripts/unreal-bridge/start.sh --ngrok")
        print("\nNext: run test_phase9.py to validate")
    else:
        print(f"FAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
