import json
import os
import boto3

TABLE = os.environ["WORLD_STATE_TABLE"]
_dynamodb = None


def _table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb").Table(TABLE)
    return _dynamodb


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    ctx = event.get("requestContext", {}).get("http", {})
    method = ctx.get("method", event.get("httpMethod", ""))
    params = event.get("pathParameters") or {}
    qs = event.get("queryStringParameters") or {}

    if method == "GET":
        object_id = params.get("object_id", "")
        if not object_id:
            return _response(400, {"error": "object_id required"})

        resp = _table().get_item(Key={"object_id": object_id})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": "not found"})
        return _response(200, {"state": item["state"]})

    if method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _response(400, {"error": "invalid JSON"})

        object_id = body.get("object_id", "")
        state = body.get("state", "")
        if not object_id or not state:
            return _response(400, {"error": "object_id and state required"})

        _table().put_item(Item={"object_id": object_id, "state": state})
        return _response(200, {"ok": True})

    return _response(405, {"error": "method not allowed"})
