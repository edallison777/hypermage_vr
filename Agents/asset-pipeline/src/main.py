"""Asset import validation, provenance tracking, licensed asset recommendations — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the AssetPipelineAgent for the Unreal VR Multiplayer System.

Your responsibilities:
1. Validate asset imports for format and metadata correctness.
2. Ensure all assets have complete provenance records — block imports missing required fields.
3. Create and maintain provenance records tracking origin, license, cost, and usage rights.
4. Recommend licensed assets when suitable. NEVER automatically purchase — always wait for manual approval.

Asset Tiers: 0=blockout, 1=placeholder/generated, 2=final/licensed.

Required Provenance Fields: origin, license, createdAt, createdBy, usageRights.
Optional: licenseUrl, sourceUrl, cost, approvedBy, approvedAt.

When recommending licensed assets: identify, provide licensing details, calculate cost, set requiresApproval=true, approved=false.

Always respond with structured JSON parseable by the orchestrator."""

@tool
def validate_asset_import(asset_path: str, asset_metadata: str) -> str:
    """Validate an asset import for format correctness and required provenance metadata."""
    return json.dumps({
        "capability": "validate_asset_import",
        "status": "processing",
        "message": f"Executing validate_asset_import...",
    })

@tool
def create_provenance_record(asset_path: str, origin: str, license: str, created_by: str) -> str:
    """Create a complete provenance record for an asset with all required fields."""
    return json.dumps({
        "capability": "create_provenance_record",
        "status": "processing",
        "message": f"Executing create_provenance_record...",
    })

@tool
def recommend_licensed_asset(asset_type: str, requirements: str) -> str:
    """Recommend licensed assets for the given type, providing full licensing details and cost. Sets requiresApproval=true."""
    return json.dumps({
        "capability": "recommend_licensed_asset",
        "status": "processing",
        "message": f"Executing recommend_licensed_asset...",
    })


@app.entrypoint
async def invoke(payload, context):
    """Asset import validation, provenance tracking, licensed asset recommendations AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[validate_asset_import, create_provenance_record, recommend_licensed_asset],
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
