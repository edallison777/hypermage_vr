"""WebSocket $disconnect handler — removes connectionId from DynamoDB."""
import os

import boto3

TABLE = os.environ["CONNECTIONS_TABLE"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)


def lambda_handler(event, _context):
    connection_id = event["requestContext"]["connectionId"]
    try:
        table.delete_item(Key={"connectionId": connection_id})
        return {"statusCode": 200, "body": "Disconnected"}
    except Exception as exc:
        print(f"ERROR disconnect: {exc}")
        return {"statusCode": 500, "body": str(exc)}
