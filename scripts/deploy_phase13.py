"""
Deploy Phase 13: Quest 3 Connects to Server
=============================================
Steps:
  1. No Terraform needed — Session API and GameLift fleet already live from Phase 4
  2. No new IAM policy needed — GameLift + SSM access already on runtime role
  3. Redeploy MultiplayerNetcode_Agent via launch_bedrock_agentcore
     (new tools: start_matchmaking, poll_matchmaking_status, get_fleet_capacity, scale_fleet)
  4. Update deployment_results.json

New features in this phase:
  - start_matchmaking: POST /matchmaking/start via Session API
  - poll_matchmaking_status: GET /matchmaking/status/{ticketId} — extracts IP+port+playerSessionId
  - get_fleet_capacity: describe GameLift fleet DESIRED/ACTIVE counts
  - scale_fleet: scale fleet up (DESIRED=1) / down (DESIRED=0)

C++ changes (no redeploy needed — part of UE5 project source):
  - HMVRGameInstance: real HTTP matchmaking (replaces mock), polling timer
  - HMVRGameInstance: ConnectToGameServer URL bug fixed (? -> &)
  - HyperMageVR.Build.cs: HTTP module added

Usage:
    cd Agents/
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe ../scripts/deploy_phase13.py
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

REGION    = "eu-west-1"
ACCOUNT   = "732231126129"
REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "Agents"


def deploy_agent() -> dict:
    config_path = AGENTS_DIR / "multiplayer-netcode" / ".bedrock_agentcore.yaml"
    agent_class = "MultiplayerNetcode_Agent"
    console     = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"\n[1/1] Deploying {agent_class} — starting CodeBuild...")
    print("  New tools: start_matchmaking, poll_matchmaking_status, get_fleet_capacity, scale_fleet")
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
    print("Phase 13 Deployment — Quest 3 Connects to Server")
    print("=" * 60)
    print("No Terraform needed — Session API + GameLift already live")
    print("No new IAM policy — GameLift access already on runtime role")
    print()
    print("Updated components:")
    print("  Agents/multiplayer-netcode/src/main.py  — real matchmaking tools")
    print("  UnrealProject/.../HMVRGameInstance.cpp  — real HTTP matchmaking")
    print("  UnrealProject/.../HyperMageVR.Build.cs  — HTTP module added")

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
        print("ALL STEPS COMPLETE — Phase 13 deployment done")
        print()
        print("To test with a live GameLift match:")
        print("  1. Scale fleet up:")
        print("     aws gamelift update-fleet-capacity \\")
        print("       --fleet-id fleet-848aced2-ac8f-405a-b120-43f4f3904983 \\")
        print("       --desired-instances 1 --region eu-west-1")
        print("  2. Run integration tests:")
        print("     PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase13.py")
        print("  3. Scale fleet back down after testing:")
        print("     aws gamelift update-fleet-capacity \\")
        print("       --fleet-id fleet-848aced2-ac8f-405a-b120-43f4f3904983 \\")
        print("       --desired-instances 0 --region eu-west-1")
    else:
        print(f"\nFAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
