"""
Asset Ingest Trigger Lambda
============================
Triggered by S3 ObjectCreated events on assets/incoming/.
Routes each upload to the appropriate processor based on file extension:

  PNG/JPG/JPEG/PSD  →  image-processor Lambda (WebP + ASTC conversion)
  FBX/OBJ/BLEND     →  ECS Fargate Blender task (→ glTF)
  PNG tagged concept →  meshy-3d Lambda (Meshy.ai image-to-3D)

Also writes a "pending" provenance record to DynamoDB so the catalogue
reflects in-flight conversions immediately.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3

S3_BUCKET             = os.environ["S3_BUCKET"]
ASSET_CATALOGUE_TABLE = os.environ["ASSET_CATALOGUE_TABLE"]
IMAGE_PROCESSOR_ARN   = os.environ["IMAGE_PROCESSOR_ARN"]
MESHY_3D_ARN          = os.environ["MESHY_3D_ARN"]
ECS_CLUSTER_ARN       = os.environ["ECS_CLUSTER_ARN"]
ECS_TASK_DEF_ARN      = os.environ["ECS_TASK_DEF_ARN"]
ECS_TASK_ROLE_ARN     = os.environ["ECS_TASK_ROLE_ARN"]
ECS_EXEC_ROLE_ARN     = os.environ["ECS_EXEC_ROLE_ARN"]
AWS_REGION            = os.environ.get("AWS_REGION_NAME", "eu-west-1")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".psd", ".webp"}
MESH_EXTENSIONS  = {".fbx", ".obj", ".blend", ".dae"}

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
lambda_  = boto3.client("lambda", region_name=AWS_REGION)
ecs      = boto3.client("ecs", region_name=AWS_REGION)
ec2      = boto3.client("ec2", region_name=AWS_REGION)


def get_default_subnet_id() -> str:
    """Return the first default subnet in the default VPC."""
    resp = ec2.describe_subnets(Filters=[{"Name": "default-for-az", "Values": ["true"]}])
    subnets = resp.get("Subnets", [])
    if not subnets:
        raise RuntimeError("No default subnets found")
    return subnets[0]["SubnetId"]


def write_pending_record(asset_id: str, s3_key: str, asset_type: str, filename: str) -> None:
    table = dynamodb.Table(ASSET_CATALOGUE_TABLE)
    table.put_item(Item={
        "assetId":   asset_id,
        "assetType": asset_type,
        "status":    "pending",
        "s3_source": f"s3://{S3_BUCKET}/{s3_key}",
        "filename":  filename,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "origin":    "uploaded",
            "license":   "pending-review",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "createdBy": "AssetIngestTrigger",
        },
    })


def route_image(asset_id: str, s3_key: str, filename: str) -> dict:
    """Invoke image-processor Lambda asynchronously."""
    payload = json.dumps({
        "asset_id":  asset_id,
        "s3_key":    s3_key,
        "s3_bucket": S3_BUCKET,
        "filename":  filename,
    })
    lambda_.invoke(
        FunctionName=IMAGE_PROCESSOR_ARN,
        InvocationType="Event",  # async
        Payload=payload,
    )
    return {"routed_to": "image-processor", "asset_id": asset_id}


def route_mesh(asset_id: str, s3_key: str, filename: str) -> dict:
    """Launch ECS Fargate Blender task — exits when conversion is complete."""
    subnet_id = get_default_subnet_id()
    ecs.run_task(
        cluster=ECS_CLUSTER_ARN,
        taskDefinition=ECS_TASK_DEF_ARN,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets":        [subnet_id],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [{
                "name": "blender-converter",
                "environment": [
                    {"name": "ASSET_ID",  "value": asset_id},
                    {"name": "S3_KEY",    "value": s3_key},
                    {"name": "S3_BUCKET", "value": S3_BUCKET},
                ],
            }]
        },
    )
    return {"routed_to": "ecs-blender", "asset_id": asset_id}


def route_concept_art(asset_id: str, s3_key: str, filename: str) -> dict:
    """Invoke meshy-3d Lambda asynchronously for image-to-3D conversion."""
    payload = json.dumps({
        "asset_id":  asset_id,
        "s3_key":    s3_key,
        "s3_bucket": S3_BUCKET,
        "filename":  filename,
    })
    lambda_.invoke(
        FunctionName=MESHY_3D_ARN,
        InvocationType="Event",
        Payload=payload,
    )
    return {"routed_to": "meshy-3d", "asset_id": asset_id}


def lambda_handler(event, _context):
    results = []
    for record in event.get("Records", []):
        s3_info  = record.get("s3", {})
        s3_key   = s3_info.get("object", {}).get("key", "")
        filename = s3_key.split("/")[-1]
        ext      = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        asset_id = str(uuid.uuid4())

        # Determine asset type
        if ext in MESH_EXTENSIONS:
            asset_type = "mesh"
        elif ext in IMAGE_EXTENSIONS:
            # Check for concept_art tag in object metadata (set by uploader via x-amz-meta-asset-type)
            asset_type = "image"
        else:
            print(f"[SKIP] Unsupported extension '{ext}' for key '{s3_key}'")
            continue

        # Write pending record to catalogue
        write_pending_record(asset_id, s3_key, asset_type, filename)

        # Route to converter
        try:
            if asset_type == "mesh":
                result = route_mesh(asset_id, s3_key, filename)
            else:
                # Check S3 metadata for concept_art hint
                s3_client = boto3.client("s3", region_name=AWS_REGION)
                head = s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
                meta = head.get("Metadata", {})
                if meta.get("asset-type") == "concept_art":
                    result = route_concept_art(asset_id, s3_key, filename)
                else:
                    result = route_image(asset_id, s3_key, filename)

            print(f"[OK] {s3_key} → {result}")
            results.append(result)

        except Exception as exc:
            print(f"[ERROR] {s3_key}: {exc}")
            # Update DynamoDB record status to failed
            dynamodb.Table(ASSET_CATALOGUE_TABLE).update_item(
                Key={"assetId": asset_id},
                UpdateExpression="SET #s = :s, errorMsg = :e",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "error", ":e": str(exc)},
            )

    return {"statusCode": 200, "routed": results}
