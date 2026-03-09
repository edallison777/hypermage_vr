"""
Deploy all 10 Hypermage VR production agents to Amazon Bedrock AgentCore.

Usage:
    cd Agents/
    python deploy_production_agents.py

Each agent is packaged as a container and deployed via CodeBuild (no local Docker needed).
Results are saved to deployment_results.json.
"""

import io
import json
import logging
import os
import sys
import textwrap
from pathlib import Path

# Force UTF-8 for all streams so SDK emoji log messages don't crash on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONIOENCODING"] = "utf-8"

logging.disable(logging.CRITICAL)

from rich.console import Console
from bedrock_agentcore_starter_toolkit.operations.runtime import launch_bedrock_agentcore

# ─── Shared constants ─────────────────────────────────────────────────────────

ACCOUNT = "732231126129"
REGION = "eu-west-1"
EXECUTION_ROLE = f"arn:aws:iam::{ACCOUNT}:role/AmazonBedrockAgentCoreSDKRuntime-eu-west-1-81c578ca1b"
S3_PATH = f"s3://bedrock-agentcore-codebuild-sources-{ACCOUNT}-{REGION}"
MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

REQUIREMENTS = """\
strands-agents>=1.13.0
bedrock-agentcore>=1.0.3
mcp>=1.19.0
strands-agents-tools>=0.2.16
"""

DOCKERFILE_TEMPLATE = """\
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \\
    UV_COMPILE_BYTECODE=1 \\
    UV_NO_PROGRESS=1 \\
    PYTHONUNBUFFERED=1 \\
    DOCKER_CONTAINER=1 \\
    AWS_REGION={region} \\
    AWS_DEFAULT_REGION={region}

COPY requirements.txt requirements.txt
RUN uv pip install -r requirements.txt

RUN uv pip install aws-opentelemetry-distro==0.12.2

ENV DOCKER_CONTAINER=1

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

COPY . .

CMD ["opentelemetry-instrument", "python", "-m", "main"]
"""

YAML_TEMPLATE = """\
default_agent: {agent_class_name}_Agent
agents:
  {agent_class_name}_Agent:
    name: {agent_class_name}_Agent
    language: python
    node_version: null
    entrypoint: {agents_dir}/{dir_name}/src/main.py
    deployment_type: container
    runtime_type: PYTHON_3_10
    platform: linux/amd64
    container_runtime: null
    source_path: {agents_dir}/{dir_name}/src
    aws:
      execution_role: {execution_role}
      execution_role_auto_create: false
      account: '{account}'
      region: {region}
      ecr_repository: null
      ecr_auto_create: true
      s3_path: {s3_path}
      s3_auto_create: false
      network_configuration:
        network_mode: PUBLIC
        network_mode_config: null
      protocol_configuration:
        server_protocol: HTTP
      observability:
        enabled: true
      lifecycle_configuration:
        idle_runtime_session_timeout: null
        max_lifetime: null
    bedrock_agentcore:
      agent_id: null
      agent_arn: null
      agent_session_id: null
    codebuild:
      project_name: null
      execution_role: null
      source_bucket: null
    memory:
      mode: NO_MEMORY
      memory_id: null
      memory_arn: null
      memory_name: null
      event_expiry_days: 30
      first_invoke_memory_check_done: false
      was_created_by_toolkit: false
    identity:
      credential_providers: []
      workload: null
    aws_jwt:
      enabled: false
      audiences: []
      signing_algorithm: ES384
      issuer_url: null
      duration_seconds: 300
    authorizer_configuration: null
    request_header_configuration: null
    oauth_configuration: null
    api_key_env_var_name: null
    api_key_credential_provider_name: null
    is_generated_by_agentcore_create: true
"""

MAIN_TEMPLATE = '''\
"""{description} — Bedrock AgentCore agent for Hypermage VR."""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """{system_prompt}"""

{tools}

@app.entrypoint
async def invoke(payload, context):
    """{description} AgentCore entrypoint."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[{tool_names}],
        system_prompt=SYSTEM_PROMPT,
    )
    prompt = payload.get("prompt", "")
    if not prompt:
        yield json.dumps({{"error": "No prompt provided"}})
        return
    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
'''

# ─── Agent definitions ────────────────────────────────────────────────────────

AGENTS = [
    {
        "dir_name": "producer-orchestrator",
        "agent_class_name": "ProducerOrchestrator",
        "description": "Task decomposition, milestone gating, reward catalog enforcement",
        "system_prompt": """You are the ProducerOrchestratorAgent, a high-level coordinator responsible for breaking down complex VR multiplayer system specifications into manageable tasks.

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

Always return structured JSON that can be parsed by the orchestrator.""",
        "capabilities": [
            ("decompose_specification", "specification: str, context: str = ''",
             "Break down a natural language VR specification into structured tasks with dependencies, agent assignments, and cost estimates."),
            ("validate_milestone", "milestone_id: str, artifacts: str",
             "Validate milestone artifacts against quality criteria and definitions of done. Returns pass/fail with details."),
            ("enforce_reward_catalog", "reward_ids: str",
             "Validate reward IDs against the rewards catalog. Rejects invalid IDs and suggests valid alternatives."),
            ("create_execution_plan", "tasks: str, constraints: str = ''",
             "Create a detailed execution plan with ordered task assignments, dependencies, and cost estimates."),
        ],
    },
    {
        "dir_name": "conversation-level-designer",
        "agent_class_name": "ConversationLevelDesigner",
        "description": "Natural language to LevelPlan conversion for VR multiplayer levels",
        "system_prompt": """You are the ConversationLevelDesignerAgent, a specialized AI for designing VR multiplayer levels for Meta Quest 3.

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

Return valid LevelPlan.json conforming to the schema. Be creative but practical.""",
        "capabilities": [
            ("generate_level_plan", "description: str, constraints: str = ''",
             "Convert a natural language level description into a structured LevelPlan.json specification."),
            ("design_zone_layout", "theme: str, player_count: int = 12",
             "Design zone layout with combat, safe, objective, and spawn zones for the given player count."),
            ("place_objectives", "level_plan: str, rewards_catalog: str",
             "Place objectives with reward IDs across zones, balancing difficulty and accessibility."),
            ("validate_level_plan", "level_plan: str",
             "Validate a LevelPlan.json against the schema and gameplay requirements."),
        ],
    },
    {
        "dir_name": "unreal-level-builder",
        "agent_class_name": "UnrealLevelBuilder",
        "description": "LevelPlan JSON to Unreal Engine map conversion",
        "system_prompt": """You are the UnrealLevelBuilderAgent, responsible for converting LevelPlan specifications into Unreal Engine maps.

Your responsibilities:
1. LevelPlan Conversion: Parse LevelPlan.json and generate Unreal Engine assets maintaining spatial relationships.
2. Blockout Geometry: Generate zone boundary boxes with color-coded materials (combat=red, safe=green, objective=blue, spawn=yellow).
3. Player Spawn Placement: Convert LevelPlan coordinates to Unreal space (Z-up, cm units) and place PlayerStart actors.
4. Objective Implementation: Place trigger volumes linked to reward IDs with visual indicators.
5. Gameplay Pass: Add basic lighting, post-process volume for VR comfort, game mode references.

Use Unreal Engine coordinate system (Z-up, cm units). Generate clean actor hierarchies. Prioritize Quest 3 performance.""",
        "capabilities": [
            ("convert_levelplan_to_map", "level_plan: str, map_name: str",
             "Convert a LevelPlan.json specification into an Unreal Engine map with all required actors."),
            ("generate_blockout_geometry", "zones: str",
             "Generate color-coded blockout geometry for each zone type (combat=red, safe=green, objective=blue, spawn=yellow)."),
            ("place_player_spawns", "spawns: str, map_name: str",
             "Place PlayerStart actors at spawn point coordinates from the LevelPlan."),
            ("implement_objectives", "objectives: str, map_name: str",
             "Create objective trigger volumes linked to reward IDs with visual indicators."),
            ("validate_map", "map_name: str",
             "Validate the generated Unreal map for correctness, performance, and completeness."),
        ],
    },
    {
        "dir_name": "gameplay-systems",
        "agent_class_name": "GameplaySystems",
        "description": "VR interactions, objective systems, and server-side reward emission",
        "system_prompt": """You are the GameplaySystemsAgent, responsible for implementing VR interactions, objective systems, and server-side reward emission.

Your responsibilities:
1. VR Interaction Systems: Implement Quest 3 grab/throw/haptic systems using OpenXR grip buttons, with distance-based highlighting and collision detection.
2. Objective System: Implement collect, reach, defeat, interact, and time objective types with server-authoritative state and progress tracking.
3. Server-Side Reward Emission: Load rewards_catalog.json on startup, validate reward IDs, emit rewards only from server, store in PlayerRewards DynamoDB table.
4. Gameplay Rules: Parse GameplayRules.json, implement trigger-action patterns with server-side evaluation.

Server authority for all gameplay state. Validate all client inputs. Optimize for Quest 3 performance.""",
        "capabilities": [
            ("implement_vr_interactions", "interaction_config: str",
             "Implement VR interaction systems (grab, throw, haptics) using OpenXR for Quest 3."),
            ("implement_objective_system", "objectives: str, level_id: str",
             "Implement objective tracking system for collect, reach, defeat, interact, and time objectives."),
            ("implement_reward_emission", "reward_ids: str, catalog_path: str",
             "Implement server-side reward emission with catalog validation and DynamoDB persistence."),
            ("implement_gameplay_rules", "rules: str",
             "Implement trigger-action gameplay rules with server-side evaluation and replication."),
        ],
    },
    {
        "dir_name": "multiplayer-netcode",
        "agent_class_name": "MultiplayerNetcode",
        "description": "Server-authoritative replication, bandwidth management, lag compensation",
        "system_prompt": """You are the MultiplayerNetcodeAgent, responsible for implementing multiplayer networking for VR gameplay.

Your responsibilities:
1. Replication Strategy: Server-authoritative with client prediction and reconciliation. Relevancy and priority-based replication.
2. Bandwidth Management: Target 50-100 KB/s per client for 10-15 players. Budget: 40% transforms, 30% events, 20% voice, 10% other. Delta compression and quantization.
3. Join/Leave Handling: JWT validation, shard capacity checks (10-15 players), world state replication to new players, graceful disconnect handling.
4. Lag Compensation: Server-side rewind for hit detection, max 200ms compensation, smooth interpolation.

Use UPROPERTY(Replicated), UFUNCTION(Server/Client Reliable/Unreliable). Quantize positions to 1cm, rotations to 1 degree.""",
        "capabilities": [
            ("implement_replication_strategy", "actor_classes: str",
             "Implement server-authoritative replication with client prediction for the given actor classes."),
            ("implement_bandwidth_management", "player_count: int = 12",
             "Configure bandwidth optimization for the given player count with delta compression and quantization."),
            ("implement_join_leave_handling", "shard_config: str",
             "Implement player join/leave handling with JWT validation, capacity checks, and state synchronization."),
            ("implement_lag_compensation", "max_compensation_ms: int = 200",
             "Implement server-side lag compensation with rewind hit detection up to the specified maximum."),
        ],
    },
    {
        "dir_name": "voice-comms",
        "agent_class_name": "VoiceComms",
        "description": "Party voice chat, mute/block controls, voice UI for VR",
        "system_prompt": """You are the VoiceCommsAgent, responsible for implementing party voice chat and player controls.

Your responsibilities:
1. Party Voice Integration: Unreal Voice Chat Interface plugin with party channel per shard, pluggable providers (Unreal Voice Chat, Vivox, Mock). Opus codec at 24-32 kbps, ~300-500 kbps total for 15 players.
2. Mute/Block Controls: Local mute (client-side), server-side block with persistence, rate limiting to prevent abuse.
3. Voice UI: Minimal VR-friendly UI with speaking indicators, wrist menu mute button, hand-tracked Quest 3 interaction.
4. Provider Configuration: Support Unreal Voice Chat (default), Vivox (enterprise), and Mock (testing).

Non-spatial party voice (all hear all). Minimize bandwidth for Quest 3 wireless.""",
        "capabilities": [
            ("implement_party_voice", "shard_id: str, provider: str = 'unreal'",
             "Implement party voice chat for a shard using the specified provider (unreal/vivox/mock)."),
            ("implement_mute_controls", "player_id: str, target_id: str, action: str",
             "Implement mute/unmute and block/unblock controls with server-side enforcement."),
            ("implement_voice_ui", "ui_style: str = 'minimal'",
             "Implement VR-friendly voice UI with speaking indicators and controls."),
            ("configure_voice_provider", "provider: str, config: str = '{}'",
             "Configure the voice provider (unreal/vivox/mock) with the given settings."),
        ],
    },
    {
        "dir_name": "tech-art-vfx-audio",
        "agent_class_name": "TechArtVFXAudio",
        "description": "Tier 1 asset generation, Niagara VFX, spatial audio, Quest 3 optimization",
        "system_prompt": """You are the TechArtVFXAudioAgent, responsible for technical art, visual effects, audio, and Quest 3 optimization.

Your responsibilities:
1. Tier 1 Asset Generation: Generate placeholder assets from 2D concept art. Asset tiers: 0=blockout, 1=auto-generated, 2=final.
2. Niagara VFX: Particle/beam/ribbon/mesh effects. Quest 3 limits: 200 particles@72FPS, 100@90FPS, 50@120FPS. GPU particles, simple materials.
3. Spatial Audio: HRTF spatial audio, distance attenuation (logarithmic), max 32 concurrent sounds. Compressed audio (OGG).
4. Quest 3 Optimization: <100 draw calls, <100k triangles, <512MB textures. ASTC compression, LOD systems, mobile materials, 1-2 dynamic lights max.

Prioritize performance over visual fidelity. Quest 3 = Snapdragon XR2 Gen 2 (mobile class hardware).""",
        "capabilities": [
            ("generate_tier1_asset", "concept_art_path: str, asset_type: str",
             "Generate a Tier 1 placeholder asset from 2D concept art for the given asset type."),
            ("implement_niagara_vfx", "effect_type: str, target_fps: int = 72",
             "Implement a Niagara VFX system within the particle budget for the target framerate."),
            ("configure_spatial_audio", "audio_asset: str, attenuation_distance: float = 2000.0",
             "Configure spatial audio with HRTF and distance attenuation for a Quest 3 audio asset."),
            ("optimize_for_quest3", "scene_stats: str",
             "Analyze scene statistics and provide optimization recommendations for Quest 3 targets."),
        ],
    },
    {
        "dir_name": "asset-pipeline",
        "agent_class_name": "AssetPipeline",
        "description": "Asset import validation, provenance tracking, licensed asset recommendations",
        "system_prompt": """You are the AssetPipelineAgent for the Unreal VR Multiplayer System.

Your responsibilities:
1. Validate asset imports for format and metadata correctness.
2. Ensure all assets have complete provenance records — block imports missing required fields.
3. Create and maintain provenance records tracking origin, license, cost, and usage rights.
4. Recommend licensed assets when suitable. NEVER automatically purchase — always wait for manual approval.

Asset Tiers: 0=blockout, 1=placeholder/generated, 2=final/licensed.

Required Provenance Fields: origin, license, createdAt, createdBy, usageRights.
Optional: licenseUrl, sourceUrl, cost, approvedBy, approvedAt.

When recommending licensed assets: identify, provide licensing details, calculate cost, set requiresApproval=true, approved=false.

Always respond with structured JSON parseable by the orchestrator.""",
        "capabilities": [
            ("validate_asset_import", "asset_path: str, asset_metadata: str",
             "Validate an asset import for format correctness and required provenance metadata."),
            ("create_provenance_record", "asset_path: str, origin: str, license: str, created_by: str",
             "Create a complete provenance record for an asset with all required fields."),
            ("recommend_licensed_asset", "asset_type: str, requirements: str",
             "Recommend licensed assets for the given type, providing full licensing details and cost. Sets requiresApproval=true."),
        ],
    },
    {
        "dir_name": "qa-agent",
        "agent_class_name": "QA",
        "description": "Test generation, VR comfort validation, networking and performance QA",
        "system_prompt": """You are the QAAgent, responsible for ensuring system quality through comprehensive testing.

Your responsibilities:
1. Unit Test Generation: Jest/Vitest (TypeScript), GTest/Catch2 (C++). AAA structure. 80% minimum coverage.
2. Integration Test Generation: Component, API, database, MCP adapter tests. Mock/staging/production environments.
3. Property-Based Tests: fast-check (TypeScript), Hypothesis (Python), RapidCheck (C++). 100+ iterations. Tag format: "Feature: unreal-vr-multiplayer-system, Property N: [description]".
4. Soak Test Support: Normal/stress/chaos scenarios. Track connection rate, latency, errors, memory, CPU, bandwidth, cost/player-hour.
5. System Validation: VR comfort (72+ FPS), networking (server authority, <200ms latency), performance (draw calls, triangles, texture memory), security (JWT, input sanitization).

Write clear, deterministic tests. Test behavior not implementation. Minimize test dependencies.""",
        "capabilities": [
            ("generate_unit_tests", "module_path: str, coverage_target: float = 0.8",
             "Generate unit tests for a code module with the target coverage percentage."),
            ("generate_integration_tests", "component: str, environment: str = 'mock'",
             "Generate integration tests for a component in the specified environment."),
            ("generate_property_tests", "property_description: str, requirement_ref: str",
             "Generate property-based tests using fast-check for the described property."),
            ("setup_soak_test", "scenario: str, duration_minutes: int = 30",
             "Configure a soak test for the given scenario (normal/stress/chaos) and duration."),
            ("validate_system", "component: str, validation_type: str",
             "Validate a system component (vr_comfort/networking/performance/security)."),
        ],
    },
    {
        "dir_name": "devops-aws",
        "agent_class_name": "DevOpsAWS",
        "description": "Terraform orchestration, CI/CD management, AWS observability",
        "system_prompt": """You are the DevOpsAWSAgent, responsible for infrastructure deployment, CI/CD, and observability.

Your responsibilities:
1. Terraform Orchestration: init/plan/apply/destroy workflows for 6 modules (cognito, dynamodb, gamelift-fleet, flexmatch, session-api, unreal-build). Remote state in S3, locking in DynamoDB. Dev=auto-approve, prod=strict approval.
2. CI/CD Pipeline Management: GitHub Actions workflows (validate_specs, build_unreal, terraform_plan, terraform_apply_dev, release_prod). Approval gates per environment.
3. Observability Setup: CloudWatch metrics (player count, connection rate, latency, cost/player-hour), structured JSON logs, X-Ray traces, CloudWatch alarms (budget, error rate, latency, auth failures), dashboards.
4. Infrastructure Deployment: Ordered deployment (networking→cognito→dynamodb→gamelift→session-api→observability) with health checks, smoke tests, cost validation, and rollback procedures.

Infrastructure as code only. Immutable infrastructure. Cost-aware. Security by default.""",
        "capabilities": [
            ("execute_terraform", "operation: str, module: str = '', environment: str = 'dev'",
             "Execute a Terraform operation (init/plan/apply/destroy) for the given module and environment."),
            ("manage_cicd_pipeline", "workflow: str, action: str, environment: str = 'dev'",
             "Manage a GitHub Actions CI/CD workflow (trigger/status/cancel) for the given environment."),
            ("setup_observability", "service: str, environment: str = 'dev'",
             "Set up CloudWatch metrics, logs, alarms, and dashboards for the given service."),
            ("deploy_infrastructure", "environment: str = 'dev', modules: str = 'all'",
             "Deploy the complete infrastructure stack for the given environment in the correct order."),
        ],
    },
    {
        "dir_name": "cost-monitor-finops",
        "agent_class_name": "CostMonitorFinOps",
        "description": "MANDATORY: Real-time cost tracking, budget enforcement, FinOps reporting",
        "system_prompt": """You are the CostMonitorFinOpsAgent, a MANDATORY financial governance agent responsible for preventing budget overruns.

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

Return structured JSON with cost records, budget status, remaining budget, and recommendations.""",
        "capabilities": [
            ("track_cost", "service: str, operation: str, cost_gbp: float, resource_id: str = ''",
             "Record a cost entry for an AWS service operation with timestamp and resource ID."),
            ("check_budget", "service: str, proposed_cost_gbp: float",
             "Check if a proposed operation cost is within budget. Returns approved/warning/blocked."),
            ("generate_cost_report", "time_period_hours: int = 24",
             "Generate a cost report with service breakdown, budget status, and projections."),
            ("load_budget_policy", "policy_path: str",
             "Load and validate a BudgetPolicy.json for the current deployment."),
            ("issue_warning", "threshold_percent: float, service: str, current_cost: float",
             "Issue a budget warning when costs approach the threshold percentage."),
        ],
    },
]


# ─── File generation helpers ──────────────────────────────────────────────────

def make_tool_source(capabilities):
    """Generate @tool decorated functions for each capability."""
    lines = []
    for func_name, params, docstring in capabilities:
        lines.append(f"@tool")
        lines.append(f"def {func_name}({params}) -> str:")
        lines.append(f'    """{docstring}"""')
        lines.append(f"    return json.dumps({{")
        lines.append(f'        "capability": "{func_name}",')
        lines.append(f'        "status": "processing",')
        lines.append(f'        "message": f"Executing {func_name}...",')
        lines.append(f"    }})")
        lines.append("")
    return "\n".join(lines)


def make_main_py(agent):
    tools_source = make_tool_source(agent["capabilities"])
    tool_names = ", ".join(cap[0] for cap in agent["capabilities"])
    # Escape triple-quotes in system prompt
    safe_prompt = agent["system_prompt"].replace('"""', "'''")
    return MAIN_TEMPLATE.format(
        description=agent["description"],
        system_prompt=safe_prompt,
        tools=tools_source,
        tool_names=tool_names,
    )


def make_yaml(agent, agents_dir):
    return YAML_TEMPLATE.format(
        agent_class_name=agent["agent_class_name"],
        dir_name=agent["dir_name"],
        agents_dir=str(agents_dir).replace("\\", "/"),
        execution_role=EXECUTION_ROLE,
        account=ACCOUNT,
        region=REGION,
        s3_path=S3_PATH,
    )


def create_agent_files(agent, agents_dir):
    """Create all files for a single agent."""
    base = agents_dir / agent["dir_name"]
    src = base / "src"
    dockerfile_dir = base / ".bedrock_agentcore" / f"{agent['agent_class_name']}_Agent"

    src.mkdir(parents=True, exist_ok=True)
    dockerfile_dir.mkdir(parents=True, exist_ok=True)

    (src / "main.py").write_text(make_main_py(agent), encoding="utf-8")
    (src / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (dockerfile_dir / "Dockerfile").write_text(
        DOCKERFILE_TEMPLATE.format(region=REGION), encoding="utf-8"
    )
    (base / ".bedrock_agentcore.yaml").write_text(
        make_yaml(agent, agents_dir), encoding="utf-8"
    )
    print(f"  [files] {agent['dir_name']}/ created")


# ─── Deployment ───────────────────────────────────────────────────────────────

def deploy_agent(agent, agents_dir):
    """Deploy a single agent to AgentCore. Returns result dict."""
    config_path = agents_dir / agent["dir_name"] / ".bedrock_agentcore.yaml"
    agent_class = f"{agent['agent_class_name']}_Agent"
    console = Console(legacy_windows=False, force_terminal=False, highlight=False)

    print(f"  [deploy] {agent_class} — starting CodeBuild...")
    try:
        result = launch_bedrock_agentcore(
            config_path=config_path,
            agent_name=agent_class,
            local=False,
            use_codebuild=True,
            console=console,
        )
        print(f"  [deploy] {agent_class} — SUCCESS agent_id={result.agent_id}")
        return {
            "agent": agent["agent_class_name"],
            "dir": agent["dir_name"],
            "agent_id": result.agent_id,
            "agent_arn": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/{result.agent_id}",
            "status": "deployed",
        }
    except Exception as exc:
        print(f"  [deploy] {agent_class} — FAILED: {exc}")
        return {
            "agent": agent["agent_class_name"],
            "dir": agent["dir_name"],
            "agent_id": None,
            "status": "failed",
            "error": str(exc),
        }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    agents_dir = Path(__file__).parent

    results = []

    for i, agent in enumerate(AGENTS, 1):
        print(f"\n[{i}/{len(AGENTS)}] {agent['agent_class_name']}_Agent")

        print(f"  Creating files...")
        create_agent_files(agent, agents_dir)

        result = deploy_agent(agent, agents_dir)
        results.append(result)

    # Save results
    results_path = agents_dir / "deployment_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Deployment complete. Results saved to {results_path}")
    print(f"{'='*60}")

    deployed = [r for r in results if r["status"] == "deployed"]
    failed = [r for r in results if r["status"] == "failed"]
    print(f"  Deployed: {len(deployed)}/{len(results)}")
    if failed:
        print(f"  Failed: {[r['agent'] for r in failed]}")

    print("\nDeployed agents:")
    for r in deployed:
        print(f"  {r['agent']:<30} {r['agent_id']}")


if __name__ == "__main__":
    main()
