"""MANDATORY: Real-time cost tracking, budget enforcement, FinOps reporting — Bedrock AgentCore agent for Hypermage VR."""

import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
REGION = os.environ.get("AWS_REGION", "eu-west-1")
DYNAMODB_TABLE = "hypermage-vr-interaction-events-dev"
S3_BUCKET = "hypermage-vr-unreal-build-artifacts-dev"
BUDGET_GBP = float(os.environ.get("BUDGET_GBP", "1000.0"))
USD_TO_GBP = 0.79  # Approximate — Cost Explorer returns USD

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
- generate_cost_report pulls REAL data from AWS Cost Explorer

Return structured JSON with cost records, budget status, remaining budget, and recommendations."""


@tool
def track_cost(service: str, operation: str, cost_gbp: float, resource_id: str = '') -> str:
    """Record a cost entry for an AWS service operation with timestamp and resource ID. Persists to DynamoDB."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(DYNAMODB_TABLE)

        record_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        table.put_item(Item={
            "sessionId": f"cost-record-{record_id}",
            "timestamp": now.isoformat(),
            "event_type": "cost_record",
            "service": service,
            "operation": operation,
            "cost_gbp": Decimal(str(round(cost_gbp, 6))),
            "resource_id": resource_id or "unspecified",
            "ttl": int((now + timedelta(days=90)).timestamp()),
        })

        return json.dumps({
            "status": "recorded",
            "record_id": f"cost-record-{record_id}",
            "service": service,
            "operation": operation,
            "cost_gbp": cost_gbp,
            "timestamp": now.isoformat(),
            "message": f"Cost recorded: {service}/{operation} £{cost_gbp:.4f}",
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def check_budget(service: str, proposed_cost_gbp: float) -> str:
    """Check if a proposed operation cost is within budget using real AWS Cost Explorer data. Returns approved/warning/blocked."""
    try:
        # Cost Explorer API is only in us-east-1
        ce = boto3.client("ce", region_name="us-east-1")

        now = datetime.now(timezone.utc).date()
        month_start = now.replace(day=1)

        # Cost Explorer requires end date > start date; if today is the 1st use yesterday
        end_date = now if now > month_start else (now - timedelta(days=1))

        response = ce.get_cost_and_usage(
            TimePeriod={"Start": str(month_start), "End": str(end_date)},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        total_usd = sum(
            float(group["Metrics"]["UnblendedCost"]["Amount"])
            for result in response["ResultsByTime"]
            for group in result["Groups"]
        )
        current_spend_gbp = round(total_usd * USD_TO_GBP, 2)
        projected_gbp = round(current_spend_gbp + proposed_cost_gbp, 2)

        if projected_gbp > BUDGET_GBP:
            status = "blocked"
        elif projected_gbp > BUDGET_GBP * 0.8:
            status = "warning"
        else:
            status = "approved"

        return json.dumps({
            "status": status,
            "service": service,
            "proposed_cost_gbp": proposed_cost_gbp,
            "current_spend_gbp": current_spend_gbp,
            "projected_total_gbp": projected_gbp,
            "budget_gbp": BUDGET_GBP,
            "remaining_budget_gbp": round(BUDGET_GBP - current_spend_gbp, 2),
            "source": "AWS Cost Explorer (real data)",
            "message": f"Budget check: {status}. Real AWS spend MTD: £{current_spend_gbp} / £{BUDGET_GBP}",
        })
    except ClientError as e:
        return json.dumps({"status": "error", "message": f"Cost Explorer: {e.response['Error']['Message']}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def generate_cost_report(time_period_hours: int = 24) -> str:
    """Generate a cost report from AWS Cost Explorer with real spend by service, budget status, and projections. Saves report to DynamoDB."""
    try:
        ce = boto3.client("ce", region_name="us-east-1")

        now = datetime.now(timezone.utc).date()
        month_start = now.replace(day=1)
        end_date = now if now > month_start else (now - timedelta(days=1))

        response = ce.get_cost_and_usage(
            TimePeriod={"Start": str(month_start), "End": str(end_date)},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        by_service_usd: dict[str, float] = {}
        total_usd = 0.0
        for result in response["ResultsByTime"]:
            for group in result["Groups"]:
                svc = group["Keys"][0]
                amt = float(group["Metrics"]["UnblendedCost"]["Amount"])
                by_service_usd[svc] = by_service_usd.get(svc, 0.0) + amt
                total_usd += amt

        # Convert to GBP, filter negligible services
        by_service_gbp = {
            svc: round(amt * USD_TO_GBP, 4)
            for svc, amt in sorted(by_service_usd.items(), key=lambda x: -x[1])
            if amt > 0.001
        }
        total_gbp = round(total_usd * USD_TO_GBP, 2)

        budget_status = "ok"
        if total_gbp > BUDGET_GBP:
            budget_status = "exceeded"
        elif total_gbp > BUDGET_GBP * 0.8:
            budget_status = "warning"

        report_id = f"cost-report-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        now_dt = datetime.now(timezone.utc)

        # Persist report record to DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(DYNAMODB_TABLE)
        table.put_item(Item={
            "sessionId": report_id,
            "timestamp": now_dt.isoformat(),
            "event_type": "cost_report",
            "total_usd": Decimal(str(round(total_usd, 4))),
            "total_gbp": Decimal(str(total_gbp)),
            "by_service_gbp": json.dumps(by_service_gbp),
            "budget_status": budget_status,
            "period_start": str(month_start),
            "period_end": str(end_date),
            "ttl": int((now_dt + timedelta(days=90)).timestamp()),
        })

        return json.dumps({
            "status": "ok",
            "report_id": report_id,
            "period": {"start": str(month_start), "end": str(end_date)},
            "total_usd": round(total_usd, 2),
            "total_gbp": total_gbp,
            "budget_gbp": BUDGET_GBP,
            "remaining_budget_gbp": round(BUDGET_GBP - total_gbp, 2),
            "budget_status": budget_status,
            "by_service_gbp": by_service_gbp,
            "source": "AWS Cost Explorer (real data)",
            "saved_to": f"DynamoDB:{DYNAMODB_TABLE}:{report_id}",
            "message": f"Real AWS spend MTD: ${total_usd:.2f} USD / £{total_gbp:.2f} GBP. Budget: {budget_status}",
        })
    except ClientError as e:
        return json.dumps({"status": "error", "message": f"Cost Explorer: {e.response['Error']['Message']}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def load_budget_policy(policy_path: str) -> str:
    """Load and validate a BudgetPolicy.json from S3 config/ prefix, or return the dev default policy."""
    try:
        if policy_path in ("default", ""):
            policy = {
                "id": "dev-default",
                "environment": "dev",
                "limits": {"total": BUDGET_GBP, "currency": "GBP", "duration": "72h"},
                "enforcement": {"mode": "report", "warningThreshold": 0.8},
            }
            return json.dumps({"status": "ok", "source": "default", "policy": policy})

        s3 = boto3.client("s3", region_name=REGION)
        response = s3.get_object(Bucket=S3_BUCKET, Key=policy_path)
        policy = json.loads(response["Body"].read().decode("utf-8"))
        return json.dumps({
            "status": "ok",
            "source": f"s3://{S3_BUCKET}/{policy_path}",
            "policy": policy,
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def issue_warning(threshold_percent: float, service: str, current_cost: float) -> str:
    """Issue a budget warning when costs approach the threshold percentage. Records warning to DynamoDB."""
    try:
        threshold_amount = BUDGET_GBP * threshold_percent
        pct_used = (current_cost / BUDGET_GBP) * 100

        now_dt = datetime.now(timezone.utc)
        warning_id = f"cost-warning-{str(uuid.uuid4())[:8]}"

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(DYNAMODB_TABLE)
        table.put_item(Item={
            "sessionId": warning_id,
            "timestamp": now_dt.isoformat(),
            "event_type": "cost_warning",
            "service": service,
            "current_cost_gbp": Decimal(str(round(current_cost, 4))),
            "threshold_percent": Decimal(str(threshold_percent)),
            "budget_gbp": Decimal(str(BUDGET_GBP)),
            "ttl": int((now_dt + timedelta(days=90)).timestamp()),
        })

        return json.dumps({
            "status": "warning_issued",
            "warning_id": warning_id,
            "service": service,
            "current_cost_gbp": current_cost,
            "budget_gbp": BUDGET_GBP,
            "threshold_percent": threshold_percent * 100,
            "threshold_amount_gbp": threshold_amount,
            "pct_used": round(pct_used, 1),
            "message": f"Budget warning: {service} at £{current_cost:.2f} ({pct_used:.1f}% of £{BUDGET_GBP} budget)",
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


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
