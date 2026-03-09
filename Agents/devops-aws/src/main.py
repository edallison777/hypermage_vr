"""Terraform orchestration, CI/CD management, AWS observability — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are the DevOpsAWSAgent, responsible for infrastructure deployment, CI/CD, and observability.

Your responsibilities:
1. Terraform Orchestration: init/plan/apply/destroy workflows for 6 modules (cognito, dynamodb, gamelift-fleet, flexmatch, session-api, unreal-build). Remote state in S3, locking in DynamoDB. Dev=auto-approve, prod=strict approval.
2. CI/CD Pipeline Management: GitHub Actions workflows (validate_specs, build_unreal, terraform_plan, terraform_apply_dev, release_prod). Approval gates per environment.
3. Observability Setup: CloudWatch metrics (player count, connection rate, latency, cost/player-hour), structured JSON logs, X-Ray traces, CloudWatch alarms (budget, error rate, latency, auth failures), dashboards.
4. Infrastructure Deployment: Ordered deployment (networking→cognito→dynamodb→gamelift→session-api→observability) with health checks, smoke tests, cost validation, and rollback procedures.

Infrastructure as code only. Immutable infrastructure. Cost-aware. Security by default."""

@tool
def execute_terraform(operation: str, module: str = '', environment: str = 'dev') -> str:
    """Execute a Terraform operation (init/plan/apply/destroy) for the given module and environment."""
    return json.dumps({
        "capability": "execute_terraform",
        "status": "processing",
        "message": f"Executing execute_terraform...",
    })

@tool
def manage_cicd_pipeline(workflow: str, action: str, environment: str = 'dev') -> str:
    """Manage a GitHub Actions CI/CD workflow (trigger/status/cancel) for the given environment."""
    return json.dumps({
        "capability": "manage_cicd_pipeline",
        "status": "processing",
        "message": f"Executing manage_cicd_pipeline...",
    })

@tool
def setup_observability(service: str, environment: str = 'dev') -> str:
    """Set up CloudWatch metrics, logs, alarms, and dashboards for the given service."""
    return json.dumps({
        "capability": "setup_observability",
        "status": "processing",
        "message": f"Executing setup_observability...",
    })

@tool
def deploy_infrastructure(environment: str = 'dev', modules: str = 'all') -> str:
    """Deploy the complete infrastructure stack for the given environment in the correct order."""
    return json.dumps({
        "capability": "deploy_infrastructure",
        "status": "processing",
        "message": f"Executing deploy_infrastructure...",
    })


@app.entrypoint
async def invoke(payload, context):
    """Terraform orchestration, CI/CD management, AWS observability AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[execute_terraform, manage_cicd_pipeline, setup_observability, deploy_infrastructure],
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
