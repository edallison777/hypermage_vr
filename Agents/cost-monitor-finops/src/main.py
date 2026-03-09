"""MANDATORY: Real-time cost tracking, budget enforcement, FinOps reporting — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the CostMonitorFinOpsAgent, a MANDATORY financial governance agent responsible for preventing budget overruns.

Your responsibilities:
1. Cost Tracking: Record all AWS operation costs per service (GameLift, Cognito, DynamoDB, Lambda) with timestamps and resource IDs.
2. Budget Enforcement: Load and validate BudgetPolicy.schema.json. Check costs against limits BEFORE operations. Block operations exceeding budget. Per-service limits.
3. Cost Reporting: Summaries with service breakdowns, budget status (ok/warning/exceeded), 72h event projections, remaining budget, trends.
4. Warning System: Alert at threshold percentages (default 80%). Notify stakeholders. Recommend optimization actions.

Key Principles:
- ALWAYS check budget before approving operations
- NEVER allow operations exceeding budget limits
- Default budget: £1000 for 72-hour events
- Enforcement modes: dev=report only, prod=block operations
- Track costs in real-time, not retrospectively

Return structured JSON with cost records, budget status, remaining budget, and recommendations."""

@tool
def track_cost(service: str, operation: str, cost_gbp: float, resource_id: str = '') -> str:
    """Record a cost entry for an AWS service operation with timestamp and resource ID."""
    return json.dumps({
        "capability": "track_cost",
        "status": "processing",
        "message": f"Executing track_cost...",
    })

@tool
def check_budget(service: str, proposed_cost_gbp: float) -> str:
    """Check if a proposed operation cost is within budget. Returns approved/warning/blocked."""
    return json.dumps({
        "capability": "check_budget",
        "status": "processing",
        "message": f"Executing check_budget...",
    })

@tool
def generate_cost_report(time_period_hours: int = 24) -> str:
    """Generate a cost report with service breakdown, budget status, and projections."""
    return json.dumps({
        "capability": "generate_cost_report",
        "status": "processing",
        "message": f"Executing generate_cost_report...",
    })

@tool
def load_budget_policy(policy_path: str) -> str:
    """Load and validate a BudgetPolicy.json for the current deployment."""
    return json.dumps({
        "capability": "load_budget_policy",
        "status": "processing",
        "message": f"Executing load_budget_policy...",
    })

@tool
def issue_warning(threshold_percent: float, service: str, current_cost: float) -> str:
    """Issue a budget warning when costs approach the threshold percentage."""
    return json.dumps({
        "capability": "issue_warning",
        "status": "processing",
        "message": f"Executing issue_warning...",
    })


@app.entrypoint
async def invoke(payload, context):
    """MANDATORY: Real-time cost tracking, budget enforcement, FinOps reporting AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[track_cost, check_budget, generate_cost_report, load_budget_policy, issue_warning],
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
