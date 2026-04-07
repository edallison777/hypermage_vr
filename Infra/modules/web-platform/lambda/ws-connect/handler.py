"""WebSocket $connect handler — records connectionId + optional sceneId in DynamoDB."""
import json
import os
import time

import boto3

TABLE = os.environ["CONNECTIONS_TABLE"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)

TTL_SECONDS = 7200  # 2-hour session TTL


def lambda_handler(event, _context):
    connection_id = event["requestContext"]["connectionId"]
    query_params  = event.get("queryStringParameters") or {}
    scene_id      = query_params.get("sceneId", "")
    participant   = query_params.get("participant", "anonymous")

    try:
        table.put_item(Item={
            "connectionId": connection_id,
            "sceneId":      scene_id,
            "participant":  participant,
            "connectedAt":  int(time.time()),
            "ttl":          int(time.time()) + TTL_SECONDS,
        })
        return {"statusCode": 200, "body": "Connected"}
    except Exception as exc:
        print(f"ERROR connect: {exc}")
        return {"statusCode": 500, "body": str(exc)}
