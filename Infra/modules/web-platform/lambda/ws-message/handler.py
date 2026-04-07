"""WebSocket $default message handler — broadcasts narrative state changes and presence.

Actions:
  join_scene      — associate this connection with a sceneId
  narrative_event — broadcast state change to all connections in same scene
  presence        — update participant position, broadcast to scene peers
  ping            — returns pong (keepalive)
"""
import json
import os

import boto3
from boto3.dynamodb.conditions import Key

CONNECTIONS_TABLE = os.environ["CONNECTIONS_TABLE"]
WEB_SCENES_TABLE  = os.environ["WEB_SCENES_TABLE"]

dynamodb  = boto3.resource("dynamodb")
conn_table  = dynamodb.Table(CONNECTIONS_TABLE)
scene_table = dynamodb.Table(WEB_SCENES_TABLE)


def _send(apigw, endpoint_url, connection_id, data):
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
    except apigw.exceptions.GoneException:
        conn_table.delete_item(Key={"connectionId": connection_id})


def _broadcast(apigw, endpoint_url, scene_id, message, exclude_id=None):
    resp = conn_table.query(
        IndexName="SceneIdIndex",
        KeyConditionExpression=Key("sceneId").eq(scene_id),
    )
    for item in resp.get("Items", []):
        cid = item["connectionId"]
        if cid != exclude_id:
            _send(apigw, endpoint_url, cid, message)


def lambda_handler(event, _context):
    ctx           = event["requestContext"]
    connection_id = ctx["connectionId"]
    domain        = ctx["domainName"]
    stage         = ctx["stage"]
    endpoint_url  = f"https://{domain}/{stage}"

    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)

    try:
        body   = json.loads(event.get("body") or "{}")
        action = body.get("action", "")

        if action == "ping":
            _send(apigw, endpoint_url, connection_id, {"action": "pong"})

        elif action == "join_scene":
            scene_id = body.get("sceneId", "")
            if scene_id:
                conn_table.update_item(
                    Key={"connectionId": connection_id},
                    UpdateExpression="SET sceneId = :s",
                    ExpressionAttributeValues={":s": scene_id},
                )
                # Notify the joining client of current scene state
                scene_resp = scene_table.get_item(Key={"sceneId": scene_id})
                scene_item = scene_resp.get("Item", {})
                _send(apigw, endpoint_url, connection_id, {
                    "action":          "scene_state",
                    "sceneId":         scene_id,
                    "narrativeState":  scene_item.get("currentNarrativeState", ""),
                    "participantCount": len(conn_table.query(
                        IndexName="SceneIdIndex",
                        KeyConditionExpression=Key("sceneId").eq(scene_id),
                    ).get("Items", [])),
                })

        elif action == "narrative_event":
            scene_id = body.get("sceneId", "")
            new_state = body.get("narrativeState", "")
            if scene_id and new_state:
                scene_table.update_item(
                    Key={"sceneId": scene_id},
                    UpdateExpression="SET currentNarrativeState = :s",
                    ExpressionAttributeValues={":s": new_state},
                )
                _broadcast(apigw, endpoint_url, scene_id, {
                    "action":         "narrative_event",
                    "sceneId":        scene_id,
                    "narrativeState": new_state,
                    "fromConnection": connection_id,
                })

        elif action == "presence":
            scene_id = body.get("sceneId", "")
            position = body.get("position", {})
            if scene_id:
                _broadcast(apigw, endpoint_url, scene_id, {
                    "action":       "presence",
                    "sceneId":      scene_id,
                    "connectionId": connection_id,
                    "participant":  body.get("participant", ""),
                    "position":     position,
                }, exclude_id=connection_id)

        return {"statusCode": 200, "body": "OK"}
    except Exception as exc:
        print(f"ERROR message handler: {exc}")
        return {"statusCode": 500, "body": str(exc)}
