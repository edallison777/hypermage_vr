"""
Meshy.ai 3D Conversion Lambda
==============================
Submits a concept-art PNG to the Meshy.ai Image-to-3D API and polls for
completion. On success, downloads the glTF output and stores it at:

  s3://{bucket}/assets/processed/{asset_id}/{stem}.glb

Updates the DynamoDB asset catalogue with status=ready and output S3 URI.

The Meshy.ai API key is read from SSM Parameter Store at startup.
If the key is not configured, the task is marked status=skipped with a note.
"""

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

S3_BUCKET              = os.environ["S3_BUCKET"]
ASSET_CATALOGUE_TABLE  = os.environ["ASSET_CATALOGUE_TABLE"]
MESHY_API_KEY_SSM_PATH = os.environ.get("MESHY_API_KEY_SSM_PATH", "/hypermage/meshy-api-key")
AWS_REGION             = os.environ.get("AWS_REGION_NAME", "eu-west-1")

MESHY_API_BASE = "https://api.meshy.ai/openapi/v2"

s3       = boto3.client("s3", region_name=AWS_REGION)
ssm      = boto3.client("ssm", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

_api_key_cache: str | None = None


def get_api_key() -> str | None:
    global _api_key_cache
    if _api_key_cache:
        return _api_key_cache
    try:
        resp = ssm.get_parameter(Name=MESHY_API_KEY_SSM_PATH, WithDecryption=True)
        _api_key_cache = resp["Parameter"]["Value"]
        return _api_key_cache
    except ssm.exceptions.ParameterNotFound:
        return None
    except Exception as exc:
        print(f"[meshy-3d] SSM key fetch failed: {exc}")
        return None


def meshy_request(method: str, path: str, body: dict | None = None, api_key: str = "") -> dict:
    url = f"{MESHY_API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def lambda_handler(event, _context):
    asset_id = event["asset_id"]
    s3_key   = event["s3_key"]
    bucket   = event.get("s3_bucket", S3_BUCKET)
    filename = event["filename"]
    stem     = filename.rsplit(".", 1)[0] if "." in filename else filename

    print(f"[meshy-3d] asset_id={asset_id} source={s3_key}")

    api_key = get_api_key()
    if not api_key:
        _update_status(asset_id, "skipped",
                       note="Meshy.ai API key not configured in SSM. Add key at "
                            f"{MESHY_API_KEY_SSM_PATH} to enable image-to-3D conversion.")
        return {"statusCode": 200, "asset_id": asset_id, "status": "skipped"}

    # Get presigned URL for source image so Meshy can fetch it
    try:
        presigned_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": s3_key}, ExpiresIn=3600
        )
    except Exception as exc:
        _update_status(asset_id, "error", str(exc))
        raise

    # Submit image-to-3D task
    try:
        task = meshy_request("POST", "/image-to-3d", {
            "image_url": presigned_url,
            "enable_pbr": True,
        }, api_key)
        task_id = task.get("result")
        print(f"[meshy-3d] Task submitted: {task_id}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        _update_status(asset_id, "error", f"Meshy API error {exc.code}: {body}")
        raise

    # Poll for completion (max 10 min)
    output_glb_url = None
    for attempt in range(60):
        time.sleep(10)
        try:
            status_resp = meshy_request("GET", f"/image-to-3d/{task_id}", api_key=api_key)
            task_status = status_resp.get("status")
            print(f"[meshy-3d] Poll {attempt+1}/60: {task_status}")

            if task_status == "SUCCEEDED":
                output_glb_url = status_resp.get("model_urls", {}).get("glb")
                break
            elif task_status in ("FAILED", "EXPIRED"):
                _update_status(asset_id, "error", f"Meshy task {task_status}")
                return {"statusCode": 500, "asset_id": asset_id, "status": task_status}
        except Exception as exc:
            print(f"[meshy-3d] Poll error: {exc}")

    if not output_glb_url:
        _update_status(asset_id, "error", "Meshy task timed out after 10 minutes")
        return {"statusCode": 500, "asset_id": asset_id, "error": "timeout"}

    # Download glTF and store in S3
    glb_key = f"assets/processed/{asset_id}/{stem}.glb"
    try:
        with urllib.request.urlopen(output_glb_url, timeout=120) as resp:
            glb_bytes = resp.read()
        s3.put_object(
            Bucket=bucket, Key=glb_key,
            Body=glb_bytes, ContentType="model/gltf-binary",
            Metadata={"source-asset-id": asset_id, "meshy-task-id": task_id},
        )
        print(f"[meshy-3d] glTF stored: {glb_key} ({len(glb_bytes)} bytes)")
    except Exception as exc:
        _update_status(asset_id, "error", f"glTF download/upload failed: {exc}")
        raise

    outputs = {"glb": f"s3://{bucket}/{glb_key}"}
    _update_status(asset_id, "ready", outputs=outputs)
    return {"statusCode": 200, "asset_id": asset_id, "outputs": outputs}


def _update_status(asset_id: str, status: str, error: str = "", note: str = "", outputs: dict = None):
    table = dynamodb.Table(ASSET_CATALOGUE_TABLE)
    expr  = "SET #s = :s, updatedAt = :u"
    vals  = {":s": status, ":u": datetime.now(timezone.utc).isoformat()}
    names = {"#s": "status"}
    if error:
        expr += ", errorMsg = :e"
        vals[":e"] = error
    if note:
        expr += ", statusNote = :n"
        vals[":n"] = note
    if outputs:
        expr += ", outputs = :o"
        vals[":o"] = outputs
    table.update_item(
        Key={"assetId": asset_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=vals,
    )
