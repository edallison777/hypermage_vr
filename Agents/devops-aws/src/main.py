"""Terraform orchestration, CI/CD management, AWS infrastructure — Bedrock AgentCore agent for Hypermage VR."""

import json
import os

import boto3
from botocore.exceptions import ClientError
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
REGION = os.environ.get("AWS_REGION", "eu-west-1")
FLEET_ID = "fleet-848aced2-ac8f-405a-b120-43f4f3904983"
TF_STATE_BUCKET = "hypermage-vr-terraform-state"
TF_STATE_KEY = "dev/terraform.tfstate"
TF_WORKING_DIR = "Infra/environments/dev"

SYSTEM_PROMPT = """You are the DevOpsAWSAgent, responsible for infrastructure deployment, CI/CD, and observability.

Your responsibilities:
1. Terraform Orchestration: Reads live Terraform state from S3 and returns execution plans for init/plan/apply/destroy. Working dir: Infra/environments/dev. Remote state: s3://hypermage-vr-terraform-state/dev/terraform.tfstate.
2. CI/CD Pipeline Management: Lists and queries CodeBuild projects (GitHub Actions workflows via CodeBuild). Reports build status.
3. Observability Setup: Describes existing CloudWatch alarms and dashboards, recommends missing ones.
4. Infrastructure Deployment: Manages GameLift fleet capacity via boto3. Fleet: fleet-848aced2. Can scale up (desired=1) or scale down (desired=0).

Infrastructure as code only. Immutable infrastructure. Cost-aware. Security by default.
Always return structured JSON with real AWS data."""


@tool
def execute_terraform(operation: str, module: str = '', environment: str = 'dev') -> str:
    """Read live Terraform state from S3 and return execution plan with real resource count and commands for the given operation (plan/apply/destroy)."""
    try:
        s3 = boto3.client("s3", region_name=REGION)

        # Read current Terraform state from S3
        try:
            response = s3.get_object(Bucket=TF_STATE_BUCKET, Key=TF_STATE_KEY)
            state_json = json.loads(response["Body"].read().decode("utf-8"))

            resources = state_json.get("resources", [])
            resource_summary: dict[str, int] = {}
            for r in resources:
                rtype = r.get("type", "unknown")
                resource_summary[rtype] = resource_summary.get(rtype, 0) + 1

            outputs = {
                k: v.get("value")
                for k, v in state_json.get("outputs", {}).items()
            }

            state_info = {
                "terraform_version": state_json.get("terraform_version", "unknown"),
                "serial": state_json.get("serial", 0),
                "resource_count": len(resources),
                "resources_by_type": resource_summary,
                "outputs": outputs,
            }
        except ClientError as e:
            state_info = {"error": f"Could not read state: {e.response['Error']['Message']}"}

        # Build commands that would be executed
        target_flag = f" -target=module.{module}" if module else ""
        commands = [
            f"cd {TF_WORKING_DIR}",
            "terraform init -backend=true",
        ]
        if operation == "plan":
            commands.append(f"terraform plan{target_flag}")
        elif operation == "apply":
            auto = "-auto-approve " if environment == "dev" else ""
            commands.append(f"terraform apply {auto}{target_flag}".strip())
        elif operation == "destroy":
            commands.append(f"terraform destroy -auto-approve{target_flag}")
        else:
            commands.append(f"terraform {operation}{target_flag}")

        resource_count = state_info.get("resource_count", "?")
        return json.dumps({
            "status": "plan_ready",
            "operation": operation,
            "module": module or "all",
            "environment": environment,
            "current_state": state_info,
            "commands_to_execute": commands,
            "working_dir": TF_WORKING_DIR,
            "state_source": f"s3://{TF_STATE_BUCKET}/{TF_STATE_KEY}",
            "message": f"Terraform {operation} plan for {environment}. Live state: {resource_count} resources.",
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def manage_cicd_pipeline(workflow: str, action: str, environment: str = 'dev') -> str:
    """List or query CodeBuild CI/CD projects. Actions: list (all projects), status (recent builds for workflow)."""
    try:
        codebuild = boto3.client("codebuild", region_name=REGION)

        if action == "list":
            response = codebuild.list_projects()
            projects = response.get("projects", [])
            return json.dumps({
                "status": "ok",
                "action": "list",
                "environment": environment,
                "codebuild_projects": projects,
                "count": len(projects),
                "message": f"Found {len(projects)} CodeBuild projects in {REGION}",
            })

        # Find matching project
        response = codebuild.list_projects()
        all_projects = response.get("projects", [])
        matching = [p for p in all_projects if workflow.lower() in p.lower()]

        if not matching:
            return json.dumps({
                "status": "not_found",
                "workflow": workflow,
                "available_projects": all_projects,
                "message": f"No CodeBuild project matching '{workflow}' found.",
            })

        project = matching[0]

        if action == "status":
            builds = codebuild.list_builds_for_project(
                projectName=project,
                sortOrder="DESCENDING",
            )
            build_ids = builds.get("ids", [])[:5]
            recent = []
            if build_ids:
                details = codebuild.batch_get_builds(ids=build_ids)
                for b in details.get("builds", []):
                    start = b.get("startTime")
                    recent.append({
                        "id": b["id"].split(":")[-1][:12],
                        "status": b["buildStatus"],
                        "start": start.isoformat() if hasattr(start, "isoformat") else str(start),
                    })

            return json.dumps({
                "status": "ok",
                "project": project,
                "recent_builds": recent,
                "message": f"Last {len(recent)} builds for {project}",
            })

        return json.dumps({
            "status": "ok",
            "project": project,
            "action": action,
            "message": f"Action '{action}' acknowledged for {project}",
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def setup_observability(service: str, environment: str = 'dev') -> str:
    """Describe existing CloudWatch alarms and dashboards for the service. Returns current state and recommendations."""
    try:
        cloudwatch = boto3.client("cloudwatch", region_name=REGION)

        alarms_response = cloudwatch.describe_alarms(
            AlarmNamePrefix="hypermage",
            MaxRecords=20,
        )
        alarms = [
            {
                "name": a["AlarmName"],
                "state": a["StateValue"],
                "metric": a.get("MetricName", ""),
                "threshold": a.get("Threshold", ""),
            }
            for a in alarms_response.get("MetricAlarms", [])
        ]

        dashboards_response = cloudwatch.list_dashboards(DashboardNamePrefix="hypermage")
        dashboards = [d["DashboardName"] for d in dashboards_response.get("DashboardEntries", [])]

        return json.dumps({
            "status": "ok",
            "service": service,
            "environment": environment,
            "region": REGION,
            "existing_alarms": alarms,
            "alarm_count": len(alarms),
            "existing_dashboards": dashboards,
            "dashboard_count": len(dashboards),
            "recommended_alarms": [
                {"name": f"hypermage-{service}-high-error-rate", "metric": "Errors", "threshold": "5%"},
                {"name": f"hypermage-{service}-high-latency", "metric": "Duration", "threshold": "200ms"},
                {"name": f"hypermage-budget-warning", "metric": "EstimatedCharges", "threshold": "£800"},
            ],
            "message": f"Observability for {service}/{environment}: {len(alarms)} alarms, {len(dashboards)} dashboards",
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@tool
def deploy_infrastructure(environment: str = 'dev', modules: str = 'all') -> str:
    """Manage GameLift fleet capacity and report real infrastructure state. Pass modules='gamelift:scale-up' or 'gamelift:scale-down' to change fleet capacity."""
    try:
        gamelift = boto3.client("gamelift", region_name=REGION)

        # Determine if we should scale
        scale_action = None
        if "scale-up" in modules:
            scale_action = "up"
        elif "scale-down" in modules:
            scale_action = "down"

        if scale_action:
            desired = 1 if scale_action == "up" else 0
            gamelift.update_fleet_capacity(
                FleetId=FLEET_ID,
                DesiredInstances=desired,
                MinSize=0,
                MaxSize=2,
            )

        # Get current fleet state
        capacity_response = gamelift.describe_fleet_capacity(FleetIds=[FLEET_ID])
        fleet_data = capacity_response.get("FleetCapacity", [{}])[0]
        capacity = fleet_data.get("InstanceCounts", {})

        attr_response = gamelift.describe_fleet_attributes(FleetIds=[FLEET_ID])
        attr_data = attr_response.get("FleetAttributes", [{}])[0]

        current_desired = capacity.get("DESIRED", 0)
        current_active = capacity.get("ACTIVE", 0)
        current_idle = capacity.get("IDLE", 0)

        result = {
            "status": "ok",
            "environment": environment,
            "modules": modules,
            "fleet_id": FLEET_ID,
            "fleet_status": attr_data.get("Status", "UNKNOWN"),
            "instance_type": attr_data.get("EC2InstanceType", "unknown"),
            "build_id": attr_data.get("BuildId", "unknown"),
            "capacity": {
                "desired": current_desired,
                "active": current_active,
                "idle": current_idle,
            },
            "region": REGION,
            "message": (
                f"Fleet {FLEET_ID}: {attr_data.get('Status')}, "
                f"desired={current_desired}, active={current_active}"
            ),
        }

        if scale_action:
            result["action_taken"] = f"Fleet scaled {scale_action}: desired set to {desired}"

        return json.dumps(result)
    except ClientError as e:
        return json.dumps({"status": "error", "message": f"GameLift: {e.response['Error']['Message']}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@app.entrypoint
async def invoke(payload, context):
    """Terraform orchestration, CI/CD management, AWS infrastructure AgentCore entrypoint."""
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
