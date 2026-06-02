"""Server-authoritative replication, matchmaking orchestration, and bandwidth management — Bedrock AgentCore agent for Hypermage VR."""

import json
import urllib.request
import urllib.error
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

import boto3

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
REGION = "eu-west-1"
FLEET_ID = "fleet-848aced2-ac8f-405a-b120-43f4f3904983"
SESSION_API_BASE = "https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"

SYSTEM_PROMPT = """You are the MultiplayerNetcodeAgent, responsible for multiplayer networking and matchmaking for Hypermage VR.

Your responsibilities:
1. Matchmaking: Start FlexMatch tickets via Session API, poll for COMPLETED status, extract IP+port+playerSessionId.
2. Fleet Management: Scale GameLift fleet up (DESIRED=1) before testing, back to 0 after.
3. Replication Strategy: Server-authoritative with client prediction and reconciliation.
4. Bandwidth Management: Target 50-100 KB/s per client for 10-15 players.
5. Lag Compensation: Server-side rewind for hit detection, max 200ms compensation.

Session API endpoints (Cognito JWT required in Authorization header):
  POST /matchmaking/start    — body: {playerId, playerAttributes}
  GET  /matchmaking/status/{ticketId} — returns status + gameSessionConnectionInfo when COMPLETED

Fleet ID: fleet-848aced2-ac8f-405a-b120-43f4f3904983 (DESIRED=0 when idle, scale to 1 for testing)."""


@tool
def start_matchmaking(player_id: str, jwt_token: str) -> str:
    """Start FlexMatch matchmaking for a player via the Session API. Returns ticketId on success."""
    url = f"{SESSION_API_BASE}/matchmaking/start"
    body = json.dumps({
        "playerId": player_id,
        "playerAttributes": {"skill": 10, "region": "eu-west-1"},
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": jwt_token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return json.dumps({
                "status": "ok",
                "ticketId": data.get("ticketId"),
                "matchmakingStatus": data.get("status"),
                "estimatedWaitTime": data.get("estimatedWaitTime"),
            })
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return json.dumps({"status": "error", "http_status": exc.code, "message": body_text})
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@tool
def poll_matchmaking_status(ticket_id: str, jwt_token: str) -> str:
    """Poll FlexMatch status for a ticket. Returns status + connection info when COMPLETED."""
    url = f"{SESSION_API_BASE}/matchmaking/status/{ticket_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": jwt_token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = {
                "status": "ok",
                "matchmakingStatus": data.get("status"),
                "statusReason": data.get("statusReason"),
                "estimatedWaitTime": data.get("estimatedWaitTime"),
            }
            if data.get("status") == "COMPLETED" and "gameSessionConnectionInfo" in data:
                conn = data["gameSessionConnectionInfo"]
                player_sessions = conn.get("matchedPlayerSessions", [])
                result["connectionInfo"] = {
                    "ipAddress": conn.get("ipAddress"),
                    "port": conn.get("port"),
                    "playerSessionId": player_sessions[0].get("playerSessionId") if player_sessions else None,
                }
            return json.dumps(result)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return json.dumps({"status": "error", "http_status": exc.code, "message": body_text})
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@tool
def get_fleet_capacity(fleet_id: str = FLEET_ID) -> str:
    """Get current GameLift fleet capacity (desired, minimum, maximum instances)."""
    try:
        client = boto3.client("gamelift", region_name=REGION)
        resp = client.describe_fleet_capacity(FleetIds=[fleet_id])
        capacities = resp.get("FleetCapacity", [])
        if not capacities:
            return json.dumps({"status": "error", "message": f"Fleet {fleet_id} not found"})
        cap = capacities[0]["InstanceCounts"]
        return json.dumps({
            "status": "ok",
            "fleetId": fleet_id,
            "desired": cap.get("DESIRED", 0),
            "minimum": cap.get("MINIMUM", 0),
            "maximum": cap.get("MAXIMUM", 0),
            "active": cap.get("ACTIVE", 0),
            "idle": cap.get("IDLE", 0),
        })
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@tool
def scale_fleet(desired_instances: int, fleet_id: str = FLEET_ID) -> str:
    """Scale the GameLift fleet to the desired number of instances (0 = idle/free, 1 = ready for testing)."""
    try:
        client = boto3.client("gamelift", region_name=REGION)
        client.update_fleet_capacity(
            FleetId=fleet_id,
            DesiredInstances=desired_instances,
        )
        return json.dumps({
            "status": "ok",
            "fleetId": fleet_id,
            "desiredInstances": desired_instances,
            "message": f"Fleet scaled to DESIRED={desired_instances}",
        })
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@tool
def implement_replication_strategy(actor_classes: str) -> str:
    """Generate server-authoritative replication config with client prediction for the given actor classes."""
    classes = [c.strip() for c in actor_classes.split(",") if c.strip()]
    return json.dumps({
        "status": "ok",
        "actorClasses": classes,
        "strategy": "server_authoritative_with_client_prediction",
        "replicationProps": "UPROPERTY(Replicated) with COND_SkipOwner where applicable",
        "movementRPC": "Server_Reliable + Client_Unreliable for position",
        "bandwidgetBudget": {"transforms": "40%", "events": "30%", "voice": "20%", "other": "10%"},
        "quantization": {"position": "1cm", "rotation": "1deg", "velocity": "1cm/s"},
    })


@tool
def implement_bandwidth_management(player_count: int = 12) -> str:
    """Configure bandwidth optimization for the given player count with delta compression and quantization."""
    per_client_kbps = min(100, max(50, int(1200 / player_count)))
    return json.dumps({
        "status": "ok",
        "playerCount": player_count,
        "perClientKbps": per_client_kbps,
        "totalServerKbps": per_client_kbps * player_count,
        "techniques": ["delta_compression", "position_quantization", "relevancy_culling", "priority_scheduling"],
        "updateRates": {"transforms": "20Hz", "game_state": "10Hz", "voice": "50Hz"},
    })


@tool
def implement_lag_compensation(max_compensation_ms: int = 200) -> str:
    """Configure server-side lag compensation with rewind hit detection."""
    return json.dumps({
        "status": "ok",
        "maxCompensationMs": max_compensation_ms,
        "technique": "server_side_rewind",
        "historyBufferMs": max_compensation_ms + 50,
        "interpolation": "hermite_cubic",
        "hitValidation": "server_authoritative_with_client_hint",
    })


@app.entrypoint
async def invoke(payload, context):
    """Multiplayer netcode + matchmaking orchestration AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[
            start_matchmaking,
            poll_matchmaking_status,
            get_fleet_capacity,
            scale_fleet,
            implement_replication_strategy,
            implement_bandwidth_management,
            implement_lag_compensation,
        ],
        system_prompt=SYSTEM_PROMPT,
    )
    prompt = payload.get("prompt", "")
    if not prompt:
        yield json.dumps({"error": "No prompt provided"})
        return
    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
