"""
Deploy Phase 6 agents to Amazon Bedrock AgentCore.

Redeploys CostMonitorFinOps and DevOpsAWS with real AWS tool implementations:
  - CostMonitorFinOps: boto3 Cost Explorer + DynamoDB
  - DevOpsAWS:         boto3 GameLift fleet management + Terraform state from S3

Usage:
    cd Agents/
    python ../scripts/deploy_phase6.py
"""

import json
import logging
import os
import sys
from pathlib import Path

# Force UTF-8 so SDK emoji log messages don't crash on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONIOENCODING"] = "utf-8"

logging.disable(logging.CRITICAL)

from rich.console import Console
from bedrock_agentcore_starter_toolkit.operations.runtime import launch_bedrock_agentcore

AGENTS_DIR = Path(__file__).parent.parent / "Agents"

PHASE6_AGENTS = [
    {
        "dir_name": "cost-monitor-finops",
        "agent_class_name": "CostMonitorFinOps",
    },
    {
        "dir_name": "devops-aws",
        "agent_class_name": "DevOpsAWS",
    },
]


def deploy_agent(agent: dict) -> dict:
    config_path = AGENTS_DIR / agent["dir_name"] / ".bedrock_agentcore.yaml"
    agent_class = f"{agent['agent_class_name']}_Agent"
    console = Console(legacy_windows=False, force_terminal=False, highlight=False)

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
        print(f"  [deploy] {agent_class} — SUCCESS  agent_id={result.agent_id}")
        return {
            "agent": agent["agent_class_name"],
            "dir": agent["dir_name"],
            "agent_id": result.agent_id,
            "agent_arn": f"arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/{result.agent_id}",
            "status": "deployed",
        }
    except Exception as exc:
        print(f"  [deploy] {agent_class} — FAILED: {exc}")
        return {
            "agent": agent["agent_class_name"],
            "dir": agent["dir_name"],
            "agent_id": None,
            "status": "failed",
            "error": str(exc),
        }


def main():
    print("Phase 6 Agent Deployment")
    print("=" * 50)
    print("Agents: CostMonitorFinOps (Cost Explorer), DevOpsAWS (GameLift + Terraform state)")
    print()

    results = []
    for i, agent in enumerate(PHASE6_AGENTS, 1):
        print(f"[{i}/{len(PHASE6_AGENTS)}] {agent['agent_class_name']}_Agent")
        result = deploy_agent(agent)
        results.append(result)
        print()

    print("=" * 50)
    deployed = [r for r in results if r["status"] == "deployed"]
    failed = [r for r in results if r["status"] == "failed"]
    print(f"Deployed: {len(deployed)}/{len(results)}")
    if failed:
        print(f"Failed:   {[r['agent'] for r in failed]}")

    print("\nDeployed agents:")
    for r in deployed:
        print(f"  {r['agent']:<30} {r['agent_id']}")

    # Update deployment_results.json with new ARNs
    results_path = AGENTS_DIR / "deployment_results.json"
    try:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

    for new in deployed:
        # Replace or append entry for this agent
        agent_name = f"{new['agent']}_Agent"
        existing = [e for e in existing if e.get("agent") != agent_name and e.get("agent") != new["agent"]]
        existing.append({
            "agent": agent_name,
            "agent_id": new["agent_id"],
            "agent_arn": new["agent_arn"],
            "status": "READY",
        })

    results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\nUpdated {results_path}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
