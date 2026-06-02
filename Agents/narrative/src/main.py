"""NarrativeAgent — Bedrock AgentCore agent for Hypermage VR.

Phase 11b: Manages narrative state transitions for LARP scenes.
Keeps VR headsets, browsers, and phones synchronised in real-time
via DynamoDB state updates and WebSocket broadcasts.

Tools:
  advance_scene       — fire a GM hook, transition narrative state, broadcast to all WS clients
  get_narrative_state — get current state and available hooks for a scene
  list_available_hooks — list all GM hooks from the ScenePlan in S3
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key as DKey
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

MODEL_ID    = "eu.anthropic.claude-sonnet-4-6"
AWS_REGION  = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

WEB_SCENES_TABLE       = os.environ.get("WEB_SCENES_TABLE", "hypermage-vr-web-scenes-dev")
WS_CONNECTIONS_TABLE   = os.environ.get("WS_CONNECTIONS_TABLE", "hypermage-vr-ws-connections-dev")
BUILD_S3_BUCKET        = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")

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
    """Convert wss://... to https://... for API GW management API calls."""
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
    """Read ScenePlan from S3 (key: scene-plans/{scene_id}/scene_plan.json)."""
    key = f"scene-plans/{scene_id}/scene_plan.json"
    try:
        obj = s3.get_object(Bucket=BUILD_S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _resolve_hook_target_state(scene_id: str, hook_name: str) -> str:
    """Find the target_state for a given hook_name from the ScenePlan.
    Falls back to hook_name if not found."""
    plan = _get_scene_plan_from_s3(scene_id)
    if not plan:
        # Try to parse gm_hooks from DynamoDB record
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

    for h in plan.get("gm_hooks", []):
        if h.get("id") == hook_name or h.get("name") == hook_name:
            return h.get("target_state", hook_name)
    return hook_name


def _broadcast_to_scene(scene_id: str, message: dict) -> int:
    """Broadcast a message to all WebSocket connections for a scene.
    Returns count of successfully notified clients."""
    mgmt_url = _ws_management_endpoint()
    if not mgmt_url:
        return 0

    # Query connections for this scene
    try:
        resp = dynamodb.Table(WS_CONNECTIONS_TABLE).query(
            IndexName="SceneIdIndex",
            KeyConditionExpression=DKey("sceneId").eq(scene_id),
            Limit=100,
        )
        connections = resp.get("Items", [])
    except Exception:
        return 0

    if not connections:
        return 0

    # Use boto3 apigatewaymanagementapi
    # The endpoint_url must be the management endpoint (stage URL, https scheme)
    # Strip trailing stage path if needed — API GW management URL format:
    # https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
    try:
        apigw = boto3.client(
            "apigatewaymanagementapi",
            region_name=AWS_REGION,
            endpoint_url=mgmt_url,
        )
    except Exception:
        return 0

    body    = json.dumps(message).encode("utf-8")
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

    # Clean up stale connections
    for conn_id in stale:
        try:
            dynamodb.Table(WS_CONNECTIONS_TABLE).delete_item(
                Key={"connectionId": conn_id}
            )
        except Exception:
            pass

    return notified


# ── Agent Tools ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the NarrativeAgent for Hypermage. You manage narrative state
transitions for LARP scenes, keeping VR headsets, browsers, and phones synchronised
in real-time.

Your responsibilities:
1. Advance scene narrative state when a GM fires a hook (advance_scene)
2. Report current narrative state and available GM hooks (get_narrative_state)
3. List all hooks defined in the ScenePlan (list_available_hooks)

State changes are broadcast instantly to all connected WebSocket clients (VR + web + phone).
The DynamoDB web-scenes record is updated so late-joining clients see the current state.

If the web-platform SSM is not configured, tools skip gracefully.
0 clients notified is valid — it means no one is connected yet."""


@tool
def advance_scene(scene_id: str, hook_name: str) -> dict:
    """Fire a GM hook: transition to the hook's target narrative state,
    update DynamoDB, and broadcast the state change to all connected WebSocket clients.

    Args:
        scene_id:  Scene ID to advance.
        hook_name: ID or name of the gm_hook to fire.

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

    # Resolve target state from ScenePlan / DynamoDB
    new_state = _resolve_hook_target_state(scene_id, hook_name)

    # Update DynamoDB currentNarrativeState
    try:
        dynamodb.Table(WEB_SCENES_TABLE).update_item(
            Key={"sceneId": scene_id},
            UpdateExpression="SET currentNarrativeState = :s, lastHookFired = :h, lastHookAt = :t",
            ExpressionAttributeValues={
                ":s": new_state,
                ":h": hook_name,
                ":t": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB update failed: {exc}"}

    # Broadcast to all connected clients
    message = {
        "action":          "narrative_event",
        "sceneId":         scene_id,
        "narrativeState":  new_state,
        "hookFired":       hook_name,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }
    clients_notified = _broadcast_to_scene(scene_id, message)

    return {
        "status":           "ok",
        "scene_id":         scene_id,
        "hook_name":        hook_name,
        "new_state":        new_state,
        "clients_notified": clients_notified,
    }


@tool
def get_narrative_state(scene_id: str) -> dict:
    """Get current narrative state and available hooks for a scene.

    Args:
        scene_id: Scene ID to query.

    Returns:
        {"status", "scene_id", "current_state", "available_hooks", "scene_name"}
    """
    record = _get_scene_record(scene_id)
    if not record:
        return {
            "status":   "skipped",
            "note":     f"Scene '{scene_id}' not found in DynamoDB",
            "scene_id": scene_id,
        }

    hooks_raw = record.get("gmHooks", "[]")
    try:
        hooks = json.loads(hooks_raw) if isinstance(hooks_raw, str) else hooks_raw
    except Exception:
        hooks = []

    available_hooks = [
        {"id": h.get("id", ""), "name": h.get("name", ""), "description": h.get("description", "")}
        for h in hooks
    ]

    return {
        "status":          "ok",
        "scene_id":        scene_id,
        "scene_name":      record.get("sceneName", ""),
        "current_state":   record.get("currentNarrativeState", ""),
        "last_hook_fired": record.get("lastHookFired", ""),
        "available_hooks": available_hooks,
    }


@tool
def list_available_hooks(scene_id: str) -> dict:
    """List all GM hooks defined in the ScenePlan for a scene.
    Reads from S3 first, falls back to DynamoDB record.

    Args:
        scene_id: Scene ID to query.

    Returns:
        {"status", "scene_id", "hooks": [{"id", "name", "description"}]}
    """
    # Try S3 ScenePlan first
    plan = _get_scene_plan_from_s3(scene_id)
    if plan:
        hooks = [
            {
                "id":           h.get("id", ""),
                "name":         h.get("name", ""),
                "description":  h.get("description", ""),
                "target_state": h.get("target_state", ""),
            }
            for h in plan.get("gm_hooks", [])
        ]
        return {
            "status":   "ok",
            "scene_id": scene_id,
            "source":   "s3_scene_plan",
            "hooks":    hooks,
        }

    # Fall back to DynamoDB record
    record = _get_scene_record(scene_id)
    if not record:
        return {
            "status":   "skipped",
            "note":     f"Scene '{scene_id}' not found in S3 or DynamoDB",
            "scene_id": scene_id,
            "hooks":    [],
        }

    hooks_raw = record.get("gmHooks", "[]")
    try:
        hooks_list = json.loads(hooks_raw) if isinstance(hooks_raw, str) else hooks_raw
    except Exception:
        hooks_list = []

    hooks = [
        {
            "id":          h.get("id", ""),
            "name":        h.get("name", ""),
            "description": h.get("description", ""),
        }
        for h in hooks_list
    ]
    return {
        "status":   "ok",
        "scene_id": scene_id,
        "source":   "dynamodb_record",
        "hooks":    hooks,
    }


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """NarrativeAgent: manage narrative state transitions for LARP scenes."""
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    agent = Agent(
        model=model,
        tools=[advance_scene, get_narrative_state, list_available_hooks],
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
