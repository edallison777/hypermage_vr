"""
Phase 20 agent redeployment — no IAM or infrastructure changes needed.
Rebuilds and pushes Docker containers for:
  1. WebPlatformAgent     — interactable object system (browser PvE game)
  2. EnvironmentDesigner  — ScenePlan schema extension + interactables prompt

Usage (from repo root):
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase20_agents.py
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

from rich.console import Console
from bedrock_agentcore_starter_toolkit.operations.runtime import launch_bedrock_agentcore

REGION     = "eu-west-1"
ACCOUNT    = "732231126129"
REPO_ROOT  = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "Agents"

AGENTS = [
    {
        "label":      "WebPlatformAgent (interactable browser game)",
        "config":     AGENTS_DIR / "web-platform" / ".bedrock_agentcore.yaml",
        "agent_name": "WebPlatform_Agent",
    },
    {
        "label":      "EnvironmentDesigner (ScenePlan schema + interactables prompt)",
        "config":     AGENTS_DIR / "conversation-level-designer" / ".bedrock_agentcore.yaml",
        "agent_name": "ConversationLevelDesigner_Agent",
    },
]


def deploy(entry: dict) -> dict:
    console = Console(legacy_windows=False, force_terminal=False, highlight=False)
    print(f"\n  Deploying {entry['label']}...")
    try:
        result   = launch_bedrock_agentcore(
            config_path=entry["config"],
            agent_name=entry["agent_name"],
            local=False,
            use_codebuild=True,
            auto_update_on_conflict=True,
            console=console,
        )
        agent_id = result.agent_id
        print(f"  OK — {entry['agent_name']}: {agent_id}")
        return {"agent": entry["agent_name"], "agent_id": agent_id, "status": "deployed"}
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return {"agent": entry["agent_name"], "status": "failed", "error": str(exc)}


def main():
    print("Phase 20 Agent Redeployment")
    print("=" * 60)
    print("Changes: interactable object system (browser) + ScenePlan schema")
    print("No Terraform or IAM changes needed.\n")

    results = []
    for entry in AGENTS:
        results.append(deploy(entry))

    print("\n" + "=" * 60)
    print("Results:")
    for r in results:
        status = "OK" if r["status"] == "deployed" else "FAILED"
        print(f"  [{status}] {r['agent']}")
        if r["status"] == "failed":
            print(f"        {r.get('error','')}")

    # Persist to deployment_results.json
    results_path = AGENTS_DIR / "deployment_results.json"
    try:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []
    for r in results:
        if r["status"] == "deployed":
            existing = [e for e in existing if e.get("agent") != r["agent"]]
            existing.append(r)
    results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    failed = [r for r in results if r["status"] == "failed"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
