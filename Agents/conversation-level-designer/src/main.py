"""Natural language to LevelPlan conversion for VR multiplayer levels — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the ConversationLevelDesignerAgent, a specialized AI for designing VR multiplayer levels for Meta Quest 3.

Your responsibilities:
1. Natural Language to LevelPlan Conversion: Transform descriptions into structured LevelPlan.json specifications with zones, spawns, and objectives.
2. Zone Layout Design: Create spatial layouts with combat, safe, objective, and spawn zones sized for 10-15 players.
3. Objective Placement: Strategically place objectives with reward IDs, balancing difficulty and gameplay flow.
4. Validation: Validate against LevelPlan.schema.json — sufficient spawn points, zone connectivity, valid reward IDs.

VR Design Principles:
- Avoid motion sickness triggers
- Provide clear navigation cues
- Design for standing/room-scale VR
- Consider Quest 3 performance limits

Return valid LevelPlan.json conforming to the schema. Be creative but practical."""

@tool
def generate_level_plan(description: str, constraints: str = '') -> str:
    """Convert a natural language level description into a structured LevelPlan.json specification."""
    return json.dumps({
        "capability": "generate_level_plan",
        "status": "processing",
        "message": f"Executing generate_level_plan...",
    })

@tool
def design_zone_layout(theme: str, player_count: int = 12) -> str:
    """Design zone layout with combat, safe, objective, and spawn zones for the given player count."""
    return json.dumps({
        "capability": "design_zone_layout",
        "status": "processing",
        "message": f"Executing design_zone_layout...",
    })

@tool
def place_objectives(level_plan: str, rewards_catalog: str) -> str:
    """Place objectives with reward IDs across zones, balancing difficulty and accessibility."""
    return json.dumps({
        "capability": "place_objectives",
        "status": "processing",
        "message": f"Executing place_objectives...",
    })

@tool
def validate_level_plan(level_plan: str) -> str:
    """Validate a LevelPlan.json against the schema and gameplay requirements."""
    return json.dumps({
        "capability": "validate_level_plan",
        "status": "processing",
        "message": f"Executing validate_level_plan...",
    })


@app.entrypoint
async def invoke(payload, context):
    """Natural language to LevelPlan conversion for VR multiplayer levels AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[generate_level_plan, design_zone_layout, place_objectives, validate_level_plan],
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
