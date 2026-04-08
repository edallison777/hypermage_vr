"""
Deploy Phase 12: UnrealLevelBuilder Full Conversion
====================================================
Steps:
  1. No Terraform needed — bridge runs on dev PC, no new cloud resources
  2. No new IAM policy needed — SSM access already covered by Phase 9
  3. Redeploy UnrealLevelBuilder_Agent via launch_bedrock_agentcore
     (new tools: convert_sceneplan_to_map, apply_atmosphere)
  4. Update deployment_results.json

New features in this phase:
  - convert_sceneplan_to_map: zones + spawns + atmosphere + asset_sources + gm_hook TriggerVolumes
  - apply_atmosphere: standalone lighting/post-process application
  - bridge.py: /scene-plan/build-full endpoint with full conversion

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase12.py
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

REGION      = "eu-west-1"
ACCOUNT     = "732231126129"
REPO_ROOT   = Path(__file__).parent.parent
AGENTS_DIR  = REPO_ROOT / "Agents"


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "unreal-level-builder" / ".bedrock_agentcore.yaml"
    agent_class = "UnrealLevelBuilder_Agent"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"\n[1/1] Deploying {agent_class} — starting CodeBuild...")
    print("  New tools: convert_sceneplan_to_map, apply_atmosphere")
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
    print("Phase 12 Deployment — UnrealLevelBuilder Full ScenePlan→UE5 Map Conversion")
    print("=" * 70)
    print("No Terraform needed — UnrealBridge runs on dev PC")
    print("No new IAM policy — SSM access already granted in Phase 9")
    print()
    print("Updated components:")
    print("  Agents/unreal-level-builder/src/main.py — convert_sceneplan_to_map, apply_atmosphere")
    print("  scripts/unreal-bridge/bridge.py         — /scene-plan/build-full endpoint")

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

        print("\n" + "=" * 70)
        print("ALL STEPS COMPLETE — Phase 12 deployment done")
        print()
        print("To use full conversion with live UE5:")
        print("  1. Open UE5 with Remote Control plugin enabled")
        print("  2. Run: scripts/unreal-bridge/start.sh --ngrok")
        print("  3. Invoke UnrealLevelBuilderAgent with convert_sceneplan_to_map()")
        print()
        print("Next: run test_phase12.py to validate")
        print("  PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase12.py")
    else:
        print(f"\nFAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
