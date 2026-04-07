"""
Blender headless FBX/OBJ/BLEND → glTF converter.
Runs inside the blender-converter ECS Fargate task.
Reads ASSET_ID, S3_KEY, S3_BUCKET from environment, downloads the source
mesh from S3, imports it in Blender, exports as glTF 2.0 (.glb), and
uploads the result to S3. Updates DynamoDB provenance on completion.
"""

import os
import sys
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Blender Python is available as `bpy` when running inside Blender
try:
    import bpy
    INSIDE_BLENDER = True
except ImportError:
    INSIDE_BLENDER = False

import boto3

ASSET_ID    = os.environ["ASSET_ID"]
S3_KEY      = os.environ["S3_KEY"]
S3_BUCKET   = os.environ["S3_BUCKET"]
TABLE_NAME  = os.environ.get("ASSET_CATALOGUE_TABLE", "hypermage-vr-asset-catalogue-dev")
AWS_REGION  = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

s3       = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def update_status(status: str, error: str = "", outputs: dict = None):
    table = dynamodb.Table(TABLE_NAME)
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
        Key={"assetId": ASSET_ID},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=vals,
    )


def convert():
    filename = S3_KEY.split("/")[-1]
    stem     = Path(filename).stem
    ext      = Path(filename).suffix.lower()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, filename)
        out_path = os.path.join(tmpdir, f"{stem}.glb")

        # Download source mesh
        print(f"[blender-converter] Downloading s3://{S3_BUCKET}/{S3_KEY}")
        s3.download_file(S3_BUCKET, S3_KEY, src_path)

        # Clear Blender scene
        bpy.ops.wm.read_factory_settings(use_empty=True)
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

        # Import based on extension
        print(f"[blender-converter] Importing {filename} ({ext})")
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=src_path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=src_path)
        elif ext in (".blend",):
            bpy.ops.wm.open_mainfile(filepath=src_path)
        elif ext == ".dae":
            bpy.ops.wm.collada_import(filepath=src_path)
        else:
            raise ValueError(f"Unsupported mesh format: {ext}")

        # Export as glTF 2.0 (.glb — binary, self-contained)
        print(f"[blender-converter] Exporting to {out_path}")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format="GLB",
            export_apply=True,        # apply modifiers
            export_materials="EXPORT",
            export_texcoords=True,
            export_normals=True,
        )

        # Upload to S3
        output_key = f"assets/processed/{ASSET_ID}/{stem}.glb"
        glb_size   = os.path.getsize(out_path)
        print(f"[blender-converter] Uploading {glb_size} bytes → s3://{S3_BUCKET}/{output_key}")
        s3.upload_file(
            out_path, S3_BUCKET, output_key,
            ExtraArgs={
                "ContentType": "model/gltf-binary",
                "Metadata": {"source-asset-id": ASSET_ID, "source-key": S3_KEY},
            }
        )

        outputs = {
            "glb": f"s3://{S3_BUCKET}/{output_key}",
            "glb_size_bytes": str(glb_size),
        }
        update_status("ready", outputs=outputs)
        print(f"[blender-converter] Done. {outputs}")
        return outputs


if __name__ == "__main__":
    if not INSIDE_BLENDER:
        print("[blender-converter] ERROR: must be run via `blender --background --python convert.py`")
        sys.exit(1)

    update_status("converting")
    try:
        convert()
    except Exception as exc:
        print(f"[blender-converter] FAILED: {exc}")
        update_status("error", str(exc))
        sys.exit(1)
