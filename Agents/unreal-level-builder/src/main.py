"""LevelPlan JSON to Unreal Engine map conversion — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the UnrealLevelBuilderAgent, responsible for converting LevelPlan specifications into Unreal Engine maps.

Your responsibilities:
1. LevelPlan Conversion: Parse LevelPlan.json and generate Unreal Engine assets maintaining spatial relationships.
2. Blockout Geometry: Generate zone boundary boxes with color-coded materials (combat=red, safe=green, objective=blue, spawn=yellow).
3. Player Spawn Placement: Convert LevelPlan coordinates to Unreal space (Z-up, cm units) and place PlayerStart actors.
4. Objective Implementation: Place trigger volumes linked to reward IDs with visual indicators.
5. Gameplay Pass: Add basic lighting, post-process volume for VR comfort, game mode references.

Use Unreal Engine coordinate system (Z-up, cm units). Generate clean actor hierarchies. Prioritize Quest 3 performance."""

@tool
def convert_levelplan_to_map(level_plan: str, map_name: str) -> str:
    """Convert a LevelPlan.json specification into an Unreal Engine map with all required actors."""
    return json.dumps({
        "capability": "convert_levelplan_to_map",
        "status": "processing",
        "message": f"Executing convert_levelplan_to_map...",
    })

@tool
def generate_blockout_geometry(zones: str) -> str:
    """Generate color-coded blockout geometry for each zone type (combat=red, safe=green, objective=blue, spawn=yellow)."""
    return json.dumps({
        "capability": "generate_blockout_geometry",
        "status": "processing",
        "message": f"Executing generate_blockout_geometry...",
    })

@tool
def place_player_spawns(spawns: str, map_name: str) -> str:
    """Place PlayerStart actors at spawn point coordinates from the LevelPlan."""
    return json.dumps({
        "capability": "place_player_spawns",
        "status": "processing",
        "message": f"Executing place_player_spawns...",
    })

@tool
def implement_objectives(objectives: str, map_name: str) -> str:
    """Create objective trigger volumes linked to reward IDs with visual indicators."""
    return json.dumps({
        "capability": "implement_objectives",
        "status": "processing",
        "message": f"Executing implement_objectives...",
    })

@tool
def validate_map(map_name: str) -> str:
    """Validate the generated Unreal map for correctness, performance, and completeness."""
    return json.dumps({
        "capability": "validate_map",
        "status": "processing",
        "message": f"Executing validate_map...",
    })


@app.entrypoint
async def invoke(payload, context):
    """LevelPlan JSON to Unreal Engine map conversion AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[convert_levelplan_to_map, generate_blockout_geometry, place_player_spawns, implement_objectives, validate_map],
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
