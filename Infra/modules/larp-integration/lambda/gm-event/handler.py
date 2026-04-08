"""GM Event Lambda Handler.

Handles POST /gm/event:
  1. Reads {scene_id, hook_name, gm_message?, token?} from request body
  2. Reads ScenePlan from S3 to resolve hook → target_state (fallback: use hook_name)
  3. Updates DynamoDB web-scenes table: currentNarrativeState
  4. Queries ws-connections for scene_id
  5. Broadcasts {action:narrative_event, sceneId, narrativeState, gmMessage} to each connection
  6. Returns {statusCode: 200, body: {clients_notified, new_state}}
"""

import json
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key as DKey

WEB_SCENES_TABLE  = os.environ.get("WEB_SCENES_TABLE", "hypermage-vr-web-scenes-dev")
CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "hypermage-vr-ws-connections-dev")
WS_ENDPOINT       = os.environ.get("WS_ENDPOINT", "")
BUILD_S3_BUCKET   = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")
AWS_REGION        = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "eu-west-1"))

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3       = boto3.client("s3", region_name=AWS_REGION)


def _json_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def _get_scene_plan(scene_id: str) -> dict | None:
    key = f"scene-plans/{scene_id}/scene_plan.json"
    try:
        obj = s3.get_object(Bucket=BUILD_S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _resolve_target_state(scene_id: str, hook_name: str) -> str:
    """Resolve hook_name to target_state via ScenePlan. Falls back to hook_name."""
    plan = _get_scene_plan(scene_id)
    if plan:
        for h in plan.get("gm_hooks", []):
            if h.get("id") == hook_name or h.get("name") == hook_name:
                return h.get("target_state", hook_name)
        return hook_name

    # Fall back to DynamoDB record gmHooks
    try:
        resp = dynamodb.Table(WEB_SCENES_TABLE).get_item(Key={"sceneId": scene_id})
        item = resp.get("Item", {})
        hooks_raw = item.get("gmHooks", "[]")
        hooks = json.loads(hooks_raw) if isinstance(hooks_raw, str) else hooks_raw
        for h in hooks:
            if h.get("id") == hook_name or h.get("name") == hook_name:
                return h.get("target_state", hook_name)
    except Exception:
        pass

    return hook_name


def _broadcast(scene_id: str, message: dict) -> int:
    """Broadcast message to all WebSocket connections for scene_id. Returns count notified."""
    if not WS_ENDPOINT:
        return 0

    try:
        resp = dynamodb.Table(CONNECTIONS_TABLE).query(
            IndexName="SceneIdIndex",
            KeyConditionExpression=DKey("sceneId").eq(scene_id),
            Limit=100,
        )
        connections = resp.get("Items", [])
    except Exception:
        return 0

    if not connections:
        return 0

    try:
        apigw = boto3.client(
            "apigatewaymanagementapi",
            region_name=AWS_REGION,
            endpoint_url=WS_ENDPOINT,
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
            dynamodb.Table(CONNECTIONS_TABLE).delete_item(
                Key={"connectionId": conn_id}
            )
        except Exception:
            pass

    return notified


def lambda_handler(event: dict, _context) -> dict:
    # Parse body
    raw_body = event.get("body", "{}")
    try:
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        else:
            body = raw_body or {}
    except Exception:
        return _json_response(400, {"error": "Invalid JSON body"})

    scene_id   = body.get("scene_id", "")
    hook_name  = body.get("hook_name", "")
    gm_message = body.get("gm_message", "")

    if not scene_id:
        return _json_response(400, {"error": "scene_id is required"})
    if not hook_name:
        return _json_response(400, {"error": "hook_name is required"})

    # Resolve target state
    new_state = _resolve_target_state(scene_id, hook_name)

    # Update DynamoDB
    now = datetime.now(timezone.utc).isoformat()
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
                ":t": now,
                ":m": gm_message,
            },
        )
    except Exception as exc:
        return _json_response(500, {"error": f"DynamoDB update failed: {str(exc)}"})

    # Broadcast to WebSocket clients
    broadcast_msg = {
        "action":         "narrative_event",
        "sceneId":        scene_id,
        "narrativeState": new_state,
        "hookFired":      hook_name,
        "timestamp":      now,
    }
    if gm_message:
        broadcast_msg["gmMessage"] = gm_message

    clients_notified = _broadcast(scene_id, broadcast_msg)

    return _json_response(200, {
        "status":           "ok",
        "scene_id":         scene_id,
        "hook_name":        hook_name,
        "new_state":        new_state,
        "clients_notified": clients_notified,
    })
