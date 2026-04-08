"""LARPIntegrationAgent — Bedrock AgentCore agent for Hypermage VR.

Phase 11b: Bridge between Game Masters and the digital world.
Receives GM commands and ensures all participants (VR + web + phone)
experience the scene changes simultaneously.

Tools:
  fire_gm_event           — fire a GM hook, advance state, broadcast to all participants
  get_connected_participants — list currently connected participants for a scene
  get_scene_status         — full status: narrative state + participant count + hooks
"""

import json
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key as DKey
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

MODEL_ID    = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION  = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

WEB_SCENES_TABLE     = os.environ.get("WEB_SCENES_TABLE", "hypermage-vr-web-scenes-dev")
WS_CONNECTIONS_TABLE = os.environ.get("WS_CONNECTIONS_TABLE", "hypermage-vr-ws-connections-dev")
BUILD_S3_BUCKET      = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")

WS_URL_SSM = "/hypermage/web-platform/ws-url"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3       = boto3.client("s3", region_name=AWS_REGION)
ssm      = boto3.client("ssm", region_name=AWS_REGION)

_ssm_cache: dict[str, str | None] = {}


def _get_ssm(name: str) -> str | None:
    if name in _ssm_cache:
        return _ssm_cache[name]
    try:
        val = ssm.get_parameter(Name=name)["Parameter"]["Value"]
        result = None if val in ("NOT_SET", "", "PLACEHOLDER") else val
    except Exception:
        result = None
    _ssm_cache[name] = result
    return result


def _ws_management_endpoint() -> str | None:
    ws_url = _get_ssm(WS_URL_SSM)
    if not ws_url:
        return None
    return ws_url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)


def _get_scene_record(scene_id: str) -> dict | None:
    try:
        resp = dynamodb.Table(WEB_SCENES_TABLE).get_item(Key={"sceneId": scene_id})
        return resp.get("Item")
    except Exception:
        return None


def _get_scene_plan_from_s3(scene_id: str) -> dict | None:
    key = f"scene-plans/{scene_id}/scene_plan.json"
    try:
        obj = s3.get_object(Bucket=BUILD_S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _resolve_hook_target_state(scene_id: str, hook_name: str) -> str:
    plan = _get_scene_plan_from_s3(scene_id)
    if plan:
        for h in plan.get("gm_hooks", []):
            if h.get("id") == hook_name or h.get("name") == hook_name:
                return h.get("target_state", hook_name)
        return hook_name

    record = _get_scene_record(scene_id)
    if record:
        hooks_raw = record.get("gmHooks", "[]")
        try:
            hooks = json.loads(hooks_raw) if isinstance(hooks_raw, str) else hooks_raw
        except Exception:
            hooks = []
        for h in hooks:
            if h.get("id") == hook_name or h.get("name") == hook_name:
                return h.get("target_state", hook_name)
    return hook_name


def _get_connections(scene_id: str) -> list[dict]:
    try:
        resp = dynamodb.Table(WS_CONNECTIONS_TABLE).query(
            IndexName="SceneIdIndex",
            KeyConditionExpression=DKey("sceneId").eq(scene_id),
            Limit=100,
        )
        return resp.get("Items", [])
    except Exception:
        return []


def _broadcast(scene_id: str, message: dict) -> int:
    mgmt_url = _ws_management_endpoint()
    if not mgmt_url:
        return 0

    connections = _get_connections(scene_id)
    if not connections:
        return 0

    try:
        apigw = boto3.client(
            "apigatewaymanagementapi",
            region_name=AWS_REGION,
            endpoint_url=mgmt_url,
        )
    except Exception:
        return 0

    body     = json.dumps(message).encode("utf-8")
    notified = 0
    stale    = []

    for conn in connections:
        conn_id = conn.get("connectionId", "")
        if not conn_id:
            continue
        try:
            apigw.post_to_connection(ConnectionId=conn_id, Data=body)
            notified += 1
        except apigw.exceptions.GoneException:
            stale.append(conn_id)
        except Exception:
            pass

    for conn_id in stale:
        try:
            dynamodb.Table(WS_CONNECTIONS_TABLE).delete_item(
                Key={"connectionId": conn_id}
            )
        except Exception:
            pass

    return notified


# ── Agent Tools ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the LARPIntegrationAgent for Hypermage. You are the bridge between
Game Masters and the digital world — you receive GM commands and ensure all participants
(VR + web + phone) experience the scene changes simultaneously.

Your responsibilities:
1. Fire GM hook events and broadcast state changes to all participants (fire_gm_event)
2. Report who is connected to a scene (get_connected_participants)
3. Give a full scene status overview for the GM (get_scene_status)

All operations are real-time. 0 clients notified is valid — participants may not be
connected yet. The state change is always persisted in DynamoDB regardless."""


@tool
def fire_gm_event(scene_id: str, hook_name: str, gm_message: str = "") -> dict:
    """Fire a GM hook event: advance narrative state and broadcast to all participants.
    Optionally include a message to show participants (e.g. "The vault opens...").

    Args:
        scene_id:   Scene ID to advance.
        hook_name:  ID or name of the gm_hook to fire.
        gm_message: Optional message to display to all participants.

    Returns:
        {"status", "scene_id", "hook_name", "new_state", "clients_notified"}
    """
    mgmt_url = _ws_management_endpoint()
    if not mgmt_url:
        return {
            "status":   "skipped",
            "note":     "Web platform SSM not configured — run deploy_phase10.py first",
            "scene_id": scene_id,
        }

    new_state = _resolve_hook_target_state(scene_id, hook_name)

    # Update DynamoDB
    try:
        dynamodb.Table(WEB_SCENES_TABLE).update_item(
            Key={"sceneId": scene_id},
            UpdateExpression=(
                "SET currentNarrativeState = :s, lastHookFired = :h, "
                "lastHookAt = :t, lastGmMessage = :m"
            ),
            ExpressionAttributeValues={
                ":s": new_state,
                ":h": hook_name,
                ":t": datetime.now(timezone.utc).isoformat(),
                ":m": gm_message,
            },
        )
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB update failed: {exc}"}

    # Build broadcast message
    message: dict = {
        "action":         "narrative_event",
        "sceneId":        scene_id,
        "narrativeState": new_state,
        "hookFired":      hook_name,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }
    if gm_message:
        message["gmMessage"] = gm_message

    clients_notified = _broadcast(scene_id, message)

    return {
        "status":           "ok",
        "scene_id":         scene_id,
        "hook_name":        hook_name,
        "new_state":        new_state,
        "gm_message":       gm_message,
        "clients_notified": clients_notified,
    }


@tool
def get_connected_participants(scene_id: str) -> dict:
    """Get list of currently connected participants for a scene.

    Args:
        scene_id: Scene ID to query.

    Returns:
        {"status", "scene_id", "participant_count", "connections": [{"connectionId", "participant", "connectedAt"}]}
    """
    connections = _get_connections(scene_id)
    participants = [
        {
            "connectionId": c.get("connectionId", ""),
            "participant":  c.get("participant", c.get("participantId", "anonymous")),
            "connectedAt":  c.get("connectedAt", ""),
            "role":         c.get("role", "player"),
        }
        for c in connections
    ]
    return {
        "status":            "ok",
        "scene_id":          scene_id,
        "participant_count": len(participants),
        "connections":       participants,
    }


@tool
def get_scene_status(scene_id: str) -> dict:
    """Get full scene status: narrative state + participant count + available hooks.

    Args:
        scene_id: Scene ID to query.

    Returns:
        {"status", "scene_id", "scene_name", "current_state", "participant_count", "available_hooks"}
    """
    record = _get_scene_record(scene_id)
    if not record:
        return {
            "status":   "skipped",
            "note":     f"Scene '{scene_id}' not found in DynamoDB",
            "scene_id": scene_id,
        }

    connections = _get_connections(scene_id)

    hooks_raw = record.get("gmHooks", "[]")
    try:
        hooks_list = json.loads(hooks_raw) if isinstance(hooks_raw, str) else hooks_raw
    except Exception:
        hooks_list = []

    available_hooks = [
        {"id": h.get("id", ""), "name": h.get("name", ""), "description": h.get("description", "")}
        for h in hooks_list
    ]

    return {
        "status":            "ok",
        "scene_id":          scene_id,
        "scene_name":        record.get("sceneName", ""),
        "current_state":     record.get("currentNarrativeState", ""),
        "last_hook_fired":   record.get("lastHookFired", ""),
        "last_gm_message":   record.get("lastGmMessage", ""),
        "participant_count": len(connections),
        "available_hooks":   available_hooks,
        "web_url":           record.get("webUrl", ""),
        "gm_panel_url":      record.get("gmPanelUrl", ""),
    }


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """LARPIntegrationAgent: GM commands → real-time participant synchronisation."""
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    agent = Agent(
        model=model,
        tools=[fire_gm_event, get_connected_participants, get_scene_status],
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
