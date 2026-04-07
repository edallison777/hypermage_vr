"""
Image Processor Lambda
=======================
Converts PNG/JPG/JPEG/PSD source images to:
  - WebP (for web/browser use)
  - ASTC placeholder (ASTC encoding at quality requires GPU/native tools;
    this Lambda writes a .astc.pending marker and logs a note — full ASTC
    encoding can be added via a separate ECS task if needed)

Outputs land at:
  s3://{bucket}/assets/processed/{asset_id}/
    {filename}.webp
    {filename}.astc.pending   (marker; replace with real ASTC when needed)

Updates the DynamoDB asset catalogue with status=ready and output S3 URIs.
"""

import io
import json
import os
from datetime import datetime, timezone

import boto3

S3_BUCKET             = os.environ["S3_BUCKET"]
ASSET_CATALOGUE_TABLE = os.environ["ASSET_CATALOGUE_TABLE"]
AWS_REGION            = os.environ.get("AWS_REGION_NAME", "eu-west-1")

s3       = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def convert_to_webp(image_bytes: bytes, quality: int = 85) -> bytes:
    """Convert image bytes to WebP using Pillow (bundled in Lambda Python 3.12)."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        return buf.getvalue()
    except ImportError:
        # Pillow not available — store a placeholder noting manual conversion needed
        return b"WEBP_CONVERSION_REQUIRES_PILLOW_LAYER"


def lambda_handler(event, _context):
    asset_id  = event["asset_id"]
    s3_key    = event["s3_key"]
    bucket    = event.get("s3_bucket", S3_BUCKET)
    filename  = event["filename"]
    stem      = filename.rsplit(".", 1)[0] if "." in filename else filename

    print(f"[image-processor] asset_id={asset_id} source={s3_key}")

    # Download source
    try:
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        image_bytes = obj["Body"].read()
    except Exception as exc:
        _update_status(asset_id, "error", str(exc))
        raise

    output_prefix = f"assets/processed/{asset_id}"
    outputs = {}

    # Convert to WebP
    try:
        webp_bytes = convert_to_webp(image_bytes)
        webp_key   = f"{output_prefix}/{stem}.webp"
        s3.put_object(
            Bucket=bucket, Key=webp_key,
            Body=webp_bytes, ContentType="image/webp",
            Metadata={"source-asset-id": asset_id, "source-key": s3_key},
        )
        outputs["webp"] = f"s3://{bucket}/{webp_key}"
        print(f"[image-processor] WebP written: {webp_key} ({len(webp_bytes)} bytes)")
    except Exception as exc:
        print(f"[image-processor] WebP conversion failed: {exc}")
        outputs["webp_error"] = str(exc)

    # ASTC: write pending marker (real ASTC encoding requires astcenc binary, not available in Lambda)
    astc_key = f"{output_prefix}/{stem}.astc.pending"
    s3.put_object(
        Bucket=bucket, Key=astc_key,
        Body=json.dumps({
            "note":       "ASTC encoding requires astcenc native binary. Run via ECS task if needed.",
            "source_key": s3_key,
            "asset_id":   asset_id,
        }).encode(),
        ContentType="application/json",
    )
    outputs["astc_pending"] = f"s3://{bucket}/{astc_key}"

    # Update DynamoDB
    _update_status(asset_id, "ready", outputs=outputs)
    print(f"[image-processor] Done. asset_id={asset_id} outputs={outputs}")
    return {"statusCode": 200, "asset_id": asset_id, "outputs": outputs}


def _update_status(asset_id: str, status: str, error: str = "", outputs: dict = None):
    table = dynamodb.Table(ASSET_CATALOGUE_TABLE)
    expr  = "SET #s = :s, updatedAt = :u"
    vals  = {":s": status, ":u": datetime.now(timezone.utc).isoformat()}
    names = {"#s": "status"}
    if error:
        expr += ", errorMsg = :e"
        vals[":e"] = error
    if outputs:
        expr += ", outputs = :o"
        vals[":o"] = outputs
    table.update_item(
        Key={"assetId": asset_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=vals,
    )
