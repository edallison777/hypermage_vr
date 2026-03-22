"""Task decomposition, milestone gating, reward catalog enforcement — Bedrock AgentCore agent for Hypermage VR."""

import json
import boto3
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

# ── Agent ARNs (eu-west-1) ────────────────────────────────────────────────────

AGENT_ARNS = {
    "ConversationLevelDesigner": "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/ConversationLevelDesigner_Agent-1ZShl1E6H5",
    "UnrealLevelBuilder":        "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/UnrealLevelBuilder_Agent-rFwJdR9uPr",
    "GameplaySystems":           "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/GameplaySystems_Agent-iBQ0EF4DP6",
    "MultiplayerNetcode":        "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/MultiplayerNetcode_Agent-GHsycuGb4A",
    "VoiceComms":                "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/VoiceComms_Agent-QOXHOyDNVk",
    "TechArtVFXAudio":           "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/TechArtVFXAudio_Agent-08HN169vef",
    "AssetPipeline":             "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/AssetPipeline_Agent-siqbOWHci2",
    "QA":                        "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/QA_Agent-2BGaK08sI3",
    "DevOpsAWS":                 "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/DevOpsAWS_Agent-tjiWN5GCZV",
    "CostMonitorFinOps":         "arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/CostMonitorFinOps_Agent-gI5m1PA2US",
}

_agentcore_client = None


def get_agentcore_client():
    global _agentcore_client
    if _agentcore_client is None:
        _agentcore_client = boto3.client("bedrock-agentcore", region_name="eu-west-1")
    return _agentcore_client


def invoke_worker_agent(agent_key: str, prompt: str) -> str:
    """Invoke a worker AgentCore agent and return its response text."""
    arn = AGENT_ARNS.get(agent_key)
    if not arn:
        return json.dumps({"error": f"Unknown agent key: {agent_key}"})

    client = get_agentcore_client()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )

    # Response body is a streaming SSE body
    raw = resp["body"].read().decode("utf-8")

    # Parse SSE lines: data: "chunk"
    chunks = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            value = line[6:].strip()
            if value.startswith('"') and value.endswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            chunks.append(value)

    return "".join(chunks)


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def decompose_specification(specification: str, context: str = '') -> str:
    """Break down a natural language VR specification into structured tasks with dependencies, agent assignments, and cost estimates."""
    prompt = (
        f"Analyse the following VR multiplayer level specification and convert it into a "
        f"structured LevelPlan.json with zones, spawns, and objectives.\n\n"
        f"Specification: {specification}"
    )
    if context:
        prompt += f"\n\nAdditional context: {context}"

    level_plan_response = invoke_worker_agent("ConversationLevelDesigner", prompt)

    return json.dumps({
        "capability": "decompose_specification",
        "status": "completed",
        "level_plan": level_plan_response,
        "tasks": [
            {"agent": "ConversationLevelDesigner", "capability": "generate_level_plan", "status": "completed"},
            {"agent": "UnrealLevelBuilder",        "capability": "generate_level",      "status": "pending"},
            {"agent": "GameplaySystems",           "capability": "implement_gameplay",   "status": "pending"},
            {"agent": "TechArtVFXAudio",           "capability": "generate_placeholder","status": "pending"},
            {"agent": "QA",                        "capability": "generate_tests",       "status": "pending"},
        ],
    })


@tool
def validate_milestone(milestone_id: str, artifacts: str) -> str:
    """Validate milestone artifacts against quality criteria and definitions of done. Returns pass/fail with details."""
    prompt = (
        f"Validate the following milestone artifacts for milestone '{milestone_id}'. "
        f"Check VR comfort requirements, multiplayer behaviour, and gameplay objectives.\n\n"
        f"Artifacts: {artifacts}"
    )
    qa_response = invoke_worker_agent("QA", prompt)

    return json.dumps({
        "capability": "validate_milestone",
        "status": "completed",
        "milestone_id": milestone_id,
        "qa_report": qa_response,
    })


@tool
def enforce_reward_catalog(reward_ids: str) -> str:
    """Validate reward IDs against the rewards catalog. Rejects invalid IDs and suggests valid alternatives."""
    # Query DynamoDB for valid reward IDs
    dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
    table = dynamodb.Table("hypermage-vr-player-rewards-dev")

    ids_to_check = [r.strip() for r in reward_ids.split(",") if r.strip()]
    valid = []
    invalid = []

    for reward_id in ids_to_check:
        try:
            resp = table.get_item(Key={"rewardId": reward_id})
            if "Item" in resp:
                valid.append(reward_id)
            else:
                invalid.append(reward_id)
        except Exception as e:
            invalid.append(reward_id)

    return json.dumps({
        "capability": "enforce_reward_catalog",
        "status": "completed",
        "valid_ids": valid,
        "invalid_ids": invalid,
        "passed": len(invalid) == 0,
        "message": (
            "All reward IDs are valid."
            if not invalid
            else f"Invalid reward IDs: {', '.join(invalid)}. Remove or replace them before proceeding."
        ),
    })


@tool
def create_execution_plan(tasks: str, constraints: str = '') -> str:
    """Create a detailed execution plan with ordered task assignments, dependencies, and cost estimates."""
    # Ask CostMonitorFinOps to validate cost envelope first
    cost_prompt = (
        f"Estimate the AWS cost for the following task set and confirm it is within budget.\n\n"
        f"Tasks: {tasks}"
    )
    if constraints:
        cost_prompt += f"\n\nConstraints: {constraints}"

    cost_report = invoke_worker_agent("CostMonitorFinOps", cost_prompt)

    return json.dumps({
        "capability": "create_execution_plan",
        "status": "completed",
        "execution_order": [
            "ConversationLevelDesigner → generate_level_plan",
            "UnrealLevelBuilder → generate_level",
            "TechArtVFXAudio → generate_placeholder (parallel with UnrealLevelBuilder)",
            "GameplaySystems → implement_gameplay",
            "MultiplayerNetcode → configure_replication",
            "VoiceComms → configure_voice",
            "AssetPipeline → import_assets",
            "QA → run_validation",
            "DevOpsAWS → deploy_gamelift",
        ],
        "cost_report": cost_report,
        "constraints_applied": constraints or "none",
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

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
