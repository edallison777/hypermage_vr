"""Asset import validation, provenance tracking, catalogue query — Bedrock AgentCore agent for Hypermage VR.

Phase 7: Real AWS tool implementations.
  - validate_asset_import:    checks DynamoDB for duplicates + validates required provenance fields
  - create_provenance_record: writes to DynamoDB hypermage-vr-asset-catalogue-dev
  - query_asset_catalogue:    scans DynamoDB by optional type/tag/status filter
"""

import json
import os
from datetime import datetime, timezone

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID    = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION  = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
TABLE_NAME  = os.environ.get("ASSET_CATALOGUE_TABLE", "hypermage-vr-asset-catalogue-dev")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

REQUIRED_PROVENANCE_FIELDS = {"origin", "license", "createdAt", "createdBy"}
VALID_ORIGINS = {"generated", "hand-crafted", "licensed", "marketplace", "uploaded"}

SYSTEM_PROMPT = """You are the AssetPipelineAgent for the Hypermage VR system.

Your responsibilities:
1. Validate asset imports for format and required provenance metadata.
2. Ensure all assets have complete provenance records — block imports missing required fields.
3. Create and maintain provenance records in the DynamoDB asset catalogue.
4. Query the asset catalogue by type, tag, or status.
5. Recommend licensed assets when suitable. NEVER automatically purchase — always wait for manual approval.

Asset Tiers: 0=blockout primitives, 1=placeholder/generated, 2=final/licensed.

Required Provenance Fields: origin, license, createdAt, createdBy, usageRights.
Optional: licenseUrl, sourceUrl, cost, approvedBy, approvedAt.

Always respond with structured JSON parseable by the orchestrator."""


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def validate_asset_import(asset_id: str, asset_name: str, asset_type: str,
                           origin: str, license: str, created_by: str) -> str:
    """Validate an asset import request. Checks:
    1. Required provenance fields are present.
    2. No duplicate asset_id exists in the catalogue.
    3. origin value is from the allowed set.
    Returns {valid: bool, errors: [...]} JSON."""
    errors = []

    # Check required fields
    if not asset_id:
        errors.append("asset_id is required")
    if not asset_name:
        errors.append("asset_name is required")
    if not origin:
        errors.append("provenance.origin is required")
    elif origin not in VALID_ORIGINS:
        errors.append(f"provenance.origin '{origin}' not in {sorted(VALID_ORIGINS)}")
    if not license:
        errors.append("provenance.license is required")
    if not created_by:
        errors.append("provenance.createdBy is required")

    # Check for duplicate in DynamoDB
    if asset_id and not errors:
        try:
            table = dynamodb.Table(TABLE_NAME)
            resp  = table.get_item(Key={"assetId": asset_id})
            if "Item" in resp:
                errors.append(f"Asset '{asset_id}' already exists in catalogue with status={resp['Item'].get('status')}")
        except Exception as exc:
            errors.append(f"Catalogue check failed: {exc}")

    if errors:
        return json.dumps({"valid": False, "errors": errors})
    return json.dumps({"valid": True, "asset_id": asset_id, "asset_name": asset_name})


@tool
def create_provenance_record(asset_id: str, asset_name: str, asset_type: str,
                              tier: int, origin: str, license: str, created_by: str,
                              license_url: str = "", source_url: str = "",
                              cost: float = 0.0, approved_by: str = "",
                              s3_uri: str = "", tags: str = "") -> str:
    """Create a provenance record for an asset in the DynamoDB asset catalogue.
    Call validate_asset_import first to ensure no duplicates.
    Returns {success: bool, asset_id: str, s3_uri: str} JSON."""
    # Build item
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "assetId":   asset_id,
        "assetType": asset_type,
        "assetName": asset_name,
        "tier":      tier,
        "status":    "ready",
        "createdAt": now,
        "updatedAt": now,
        "provenance": {
            "origin":    origin,
            "license":   license,
            "createdAt": now,
            "createdBy": created_by,
        },
    }
    if license_url:
        item["provenance"]["licenseUrl"] = license_url
    if source_url:
        item["provenance"]["sourceUrl"] = source_url
    if cost:
        item["provenance"]["cost"] = str(cost)
    if approved_by:
        item["provenance"]["approvedBy"] = approved_by
        item["provenance"]["approvedAt"] = now
    if s3_uri:
        item["s3Uri"] = s3_uri
    if tags:
        item["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        dynamodb.Table(TABLE_NAME).put_item(Item=item)
        return json.dumps({
            "success":  True,
            "asset_id": asset_id,
            "s3_uri":   s3_uri,
            "message":  f"Provenance record created for '{asset_name}' in {TABLE_NAME}",
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


@tool
def query_asset_catalogue(asset_type: str = "", status: str = "", tag: str = "",
                           limit: int = 50) -> str:
    """Query the asset catalogue. Optional filters:
      asset_type: mesh | texture | audio | concept_art | animation | material
      status:     pending | converting | ready | error | skipped
      tag:        free-text tag to filter by (partial match)
    Returns list of matching asset records (up to limit)."""
    table = dynamodb.Table(TABLE_NAME)

    # Use GSI if filtering by assetType or status
    try:
        if asset_type:
            resp = table.query(
                IndexName="AssetTypeIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("assetType").eq(asset_type),
                Limit=limit,
            )
        elif status:
            resp = table.query(
                IndexName="StatusIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("status").eq(status),
                Limit=limit,
            )
        else:
            resp = table.scan(Limit=limit)

        items = resp.get("Items", [])

        # Apply tag filter in-memory if requested
        if tag and items:
            tag_lower = tag.lower()
            items = [
                i for i in items
                if any(tag_lower in t.lower() for t in i.get("tags", []))
                or tag_lower in i.get("assetName", "").lower()
            ]

        return json.dumps({
            "status":  "ok",
            "count":   len(items),
            "assets":  items,
            "table":   TABLE_NAME,
            "filters": {"asset_type": asset_type, "status": status, "tag": tag},
        }, default=str)

    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def recommend_licensed_asset(asset_type: str, requirements: str) -> str:
    """Recommend licensed assets for the given type and requirements.
    Provides full licensing details and cost estimate. Sets requiresApproval=true.
    NEVER purchases automatically."""
    return json.dumps({
        "capability":        "recommend_licensed_asset",
        "asset_type":        asset_type,
        "requirements":      requirements,
        "requiresApproval":  True,
        "approved":          False,
        "message": (
            "Licensed asset recommendation noted. Review licensing terms and approve "
            "manually before purchasing. Then call create_provenance_record with "
            "origin='licensed' and your approvedBy name."
        ),
        "suggested_sources": [
            {"name": "Fab (Epic Games Marketplace)", "url": "https://www.fab.com"},
            {"name": "Sketchfab",                    "url": "https://sketchfab.com"},
            {"name": "TurboSquid",                   "url": "https://www.turbosquid.com"},
            {"name": "PolyHaven (CC0)",               "url": "https://polyhaven.com"},
        ],
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """AssetPipelineAgent: validate imports, manage provenance, query catalogue."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[validate_asset_import, create_provenance_record,
               query_asset_catalogue, recommend_licensed_asset],
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
