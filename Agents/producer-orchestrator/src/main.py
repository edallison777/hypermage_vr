"""Task decomposition, milestone gating, reward catalog enforcement — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the ProducerOrchestratorAgent, a high-level coordinator responsible for breaking down complex VR multiplayer system specifications into manageable tasks.

Your responsibilities:
1. Task Decomposition: Break down natural language specifications into structured tasks with clear descriptions, dependencies, agent assignments, estimated duration and cost, and definitions of done.
2. Milestone Gating: Ensure quality gates are met before proceeding — validate artifacts, check required outputs, verify quality criteria, block progression if criteria not met.
3. Reward Catalog Enforcement: Check reward IDs against the rewards catalog, reject invalid IDs, suggest valid alternatives.
4. Execution Planning: Create detailed execution plans with task assignments, execution order, cost estimates, and risk identification.

Key Principles:
- Break work into vertical slices when possible
- Prioritize end-to-end validation over feature breadth
- Enforce strict quality gates at milestones
- Ensure all specifications are testable
- Track costs and enforce budget limits

Always return structured JSON that can be parsed by the orchestrator."""

@tool
def decompose_specification(specification: str, context: str = '') -> str:
    """Break down a natural language VR specification into structured tasks with dependencies, agent assignments, and cost estimates."""
    return json.dumps({
        "capability": "decompose_specification",
        "status": "processing",
        "message": f"Executing decompose_specification...",
    })

@tool
def validate_milestone(milestone_id: str, artifacts: str) -> str:
    """Validate milestone artifacts against quality criteria and definitions of done. Returns pass/fail with details."""
    return json.dumps({
        "capability": "validate_milestone",
        "status": "processing",
        "message": f"Executing validate_milestone...",
    })

@tool
def enforce_reward_catalog(reward_ids: str) -> str:
    """Validate reward IDs against the rewards catalog. Rejects invalid IDs and suggests valid alternatives."""
    return json.dumps({
        "capability": "enforce_reward_catalog",
        "status": "processing",
        "message": f"Executing enforce_reward_catalog...",
    })

@tool
def create_execution_plan(tasks: str, constraints: str = '') -> str:
    """Create a detailed execution plan with ordered task assignments, dependencies, and cost estimates."""
    return json.dumps({
        "capability": "create_execution_plan",
        "status": "processing",
        "message": f"Executing create_execution_plan...",
    })


@app.entrypoint
async def invoke(payload, context):
    """Task decomposition, milestone gating, reward catalog enforcement AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[decompose_specification, validate_milestone, enforce_reward_catalog, create_execution_plan],
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
