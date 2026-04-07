"""
Deploy Phase 8: Audio Production Pipeline
==========================================
Steps:
  1. Terraform apply (audio-pipeline module) — creates DynamoDB + SSM placeholders
  2. Attach Phase8AudioPipelinePolicy to the AgentCore runtime role
  3. Redeploy TechArtVFXAudioAgent (with real ElevenLabs + Stability AI tools)

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase8.py

Cost safety: DynamoDB on-demand + API-per-call only. No Lambda, no ECS, no EC2.
GameLift fleet stays at DESIRED=0.

To enable real audio generation, set API keys in SSM after deployment:
    aws ssm put-parameter --name /hypermage/elevenlabs-api-key \\
        --value YOUR_KEY --type SecureString --overwrite --region eu-west-1
    aws ssm put-parameter --name /hypermage/stability-api-key \\
        --value YOUR_KEY --type SecureString --overwrite --region eu-west-1
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

PHASE8_POLICY_NAME = "Phase8AudioPipelinePolicy"
PHASE8_POLICY_DOC  = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AudioAssetsTableAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                "dynamodb:Query", "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-audio-assets-dev",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/hypermage-vr-audio-assets-dev/index/*",
            ],
        },
        {
            "Sid": "AudioS3Access",
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:GetObject"],
            "Resource": "arn:aws:s3:::hypermage-vr-unreal-build-artifacts-dev/audio/*",
        },
        {
            "Sid": "AudioSSMKeys",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": [
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/elevenlabs-api-key",
                f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/hypermage/stability-api-key",
            ],
        },
    ],
})


def run_terraform() -> bool:
    print("\n[1/3] Terraform apply (audio-pipeline module)...")
    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-target=module.audio_pipeline"],
            cwd=str(TERRAFORM_DIR),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  FAILED:\n{result.stderr[-2000:]}")
            return False
        print("  OK — audio-pipeline resources applied")
        return True
    except FileNotFoundError:
        print("  SKIP — terraform not in PATH, run manually:")
        print(f"    cd {TERRAFORM_DIR}")
        print("    terraform apply -auto-approve -target=module.audio_pipeline")
        return True


def attach_iam_policy() -> bool:
    print("\n[2/3] Attaching Phase8AudioPipelinePolicy to runtime role...")
    iam       = boto3.client("iam", region_name=REGION)
    role_name = RUNTIME_ROLE.split("/")[-1]
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=PHASE8_POLICY_NAME,
            PolicyDocument=PHASE8_POLICY_DOC,
        )
        print(f"  OK — {PHASE8_POLICY_NAME} attached to {role_name}")
        return True
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return False


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "tech-art-vfx-audio" / ".bedrock_agentcore.yaml"
    agent_class = "TechArtVFXAudio_Agent"
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
    print("Phase 8 Deployment — Audio Production Pipeline")
    print("=" * 60)
    print("Cost-safe: DynamoDB on-demand + API-per-call. No Lambda/ECS/EC2.")
    print("GameLift fleet: stays at DESIRED=0")

    if not run_terraform():
        sys.exit(1)
    if not attach_iam_policy():
        sys.exit(1)

    result = deploy_agent()

    # Update deployment_results.json
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
        print("ALL STEPS COMPLETE — Phase 8 deployment done")
        print("\nOptional: set API keys to enable real audio generation:")
        print("  aws ssm put-parameter --name /hypermage/elevenlabs-api-key \\")
        print("      --value YOUR_KEY --type SecureString --overwrite --region eu-west-1")
        print("  aws ssm put-parameter --name /hypermage/stability-api-key \\")
        print("      --value YOUR_KEY --type SecureString --overwrite --region eu-west-1")
        print("\nNext: run test_phase8.py to validate end-to-end")
    else:
        print(f"FAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
