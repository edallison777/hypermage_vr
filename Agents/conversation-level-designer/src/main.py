"""EnvironmentDesigner — natural language to ScenePlan conversion for Hypermage VR/Web.

Supports LARP scenes, cyberspace nodes, ritual spaces, and any experiential environment.
Outputs validated ScenePlan.json saved to S3, usable by both UE5 (VR) and Babylon.js (web).
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import jsonschema
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
S3_BUCKET = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")
S3_PREFIX = "scene-plans"

# Load schema and rewards catalog at startup (bundled alongside main.py in container)
_schema_path = Path(__file__).parent / "ScenePlan.schema.json"
_catalog_path = Path(__file__).parent / "rewards_catalog.json"

with open(_schema_path) as f:
    SCENE_PLAN_SCHEMA = json.load(f)

with open(_catalog_path) as f:
    _catalog_data = json.load(f)
    VALID_REWARD_IDS = {r["id"] for r in _catalog_data.get("rewards", [])}

SYSTEM_PROMPT = """You are the EnvironmentDesigner for Hypermage — a creative AI that designs
immersive environments for LARP productions, VR experiences, and web interactive scenes.

You think in terms of ATMOSPHERE, NARRATIVE, and EXPERIENCE — not traditional game mechanics.
There is no assumed win/lose condition. "Objectives" might be "find the oracle", "survive the
ritual", "witness the prophecy", or "choose your allegiance". The environment should be
beautiful, atmospheric, and dramatically appropriate.

You design for two platforms simultaneously:
- VR (Meta Quest 3 via Unreal Engine 5) — immersive, spatial, embodied
- Web (Babylon.js browser) — accessible, shareable, no headset required

Your output MUST be a valid JSON object conforming to ScenePlan.schema.json.

Design principles:
- Scene types: exploration, ritual, cyberspace, social, combat, sanctuary, hybrid
- Zones are named spaces with character: "The Oracle Chamber", "ICE Wall Alpha", "Ritual Circle"
- Narrative states give GMs control: scenes have before/during/after states the GM advances
- GM hooks are the GM's toolkit: named triggers that change the world in real-time
- Atmosphere is everything: lighting, audio, VFX, post-processing all serve the emotional tone
- Quest 3 limits: vfx_density max "medium", 1-2 dynamic lights, keep zones reasonably sized
- Coordinates use Unreal units (cm). A typical room = 1000x1000x400 units. A large arena = 5000x5000.
- participant_spawns should face inward toward the scene centre (yaw toward 0,0,0 by default)
- Always include at least 2 narrative_states (an initial state and at least one transition target)
- GM hooks must match transition trigger_hook_ids exactly
- reward_id values MUST come from the valid rewards catalog (use get_available_rewards() first)

When given a description:
1. Call get_available_rewards() to know which reward IDs are valid
2. Reason through the scene design — zones, atmosphere, narrative arc, GM hooks
3. Generate the complete ScenePlan JSON
4. Call validate_scene_plan(scene_plan_json) to check it
5. Fix any validation errors and re-validate
6. Call save_scene_plan(scene_plan_json) to persist to S3
7. Return the final ScenePlan JSON with the S3 URI"""


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_available_rewards() -> str:
    """Return all valid reward IDs from the rewards catalog. Always call this before assigning reward_id values to objectives."""
    rewards = [
        {"id": r["id"], "name": r["name"], "description": r["description"], "category": r["category"]}
        for r in _catalog_data.get("rewards", [])
    ]
    return json.dumps({
        "status": "ok",
        "count": len(rewards),
        "rewards": rewards,
        "note": "Only use reward IDs from this list in ScenePlan objectives."
    })


@tool
def validate_scene_plan(scene_plan_json: str) -> str:
    """Validate a ScenePlan JSON string against the ScenePlan schema. Returns validation errors or confirms validity.
    Fix all errors before calling save_scene_plan."""
    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as e:
        return json.dumps({"valid": False, "errors": [f"Invalid JSON: {e}"]})

    validator = jsonschema.Draft7Validator(SCENE_PLAN_SCHEMA)
    errors = [
        {"path": " > ".join(str(p) for p in err.absolute_path) or "(root)", "message": err.message}
        for err in sorted(validator.iter_errors(plan), key=lambda e: list(e.absolute_path))
    ]

    if errors:
        return json.dumps({"valid": False, "error_count": len(errors), "errors": errors})

    # Cross-reference checks beyond JSON schema
    warnings = []
    state_ids = {s["id"] for s in plan.get("narrative_states", [])}
    hook_ids = {h["id"] for h in plan.get("gm_hooks", [])}
    zone_ids = {z["id"] for z in plan.get("zones", [])}
    initial_states = [s for s in plan.get("narrative_states", []) if s.get("is_initial")]

    if len(initial_states) != 1:
        errors.append({"path": "narrative_states", "message": f"Exactly one narrative state must have is_initial=true, found {len(initial_states)}"})

    initial_state_ref = plan.get("narrative_context", {}).get("initial_state")
    if initial_state_ref and initial_state_ref not in state_ids:
        errors.append({"path": "narrative_context.initial_state", "message": f"'{initial_state_ref}' not found in narrative_states"})

    for state in plan.get("narrative_states", []):
        for t in state.get("transitions", []):
            if t.get("trigger_hook_id") not in hook_ids:
                errors.append({"path": f"narrative_states[{state['id']}].transitions", "message": f"hook '{t.get('trigger_hook_id')}' not found in gm_hooks"})
            if t.get("next_state_id") not in state_ids:
                errors.append({"path": f"narrative_states[{state['id']}].transitions", "message": f"next_state '{t.get('next_state_id')}' not found in narrative_states"})

    for obj in plan.get("objectives", []):
        if "reward_id" in obj and obj["reward_id"] not in VALID_REWARD_IDS:
            warnings.append(f"objective '{obj['id']}' uses reward_id '{obj['reward_id']}' which is not in the catalog")
        if "zone_id" in obj and obj["zone_id"] not in zone_ids:
            warnings.append(f"objective '{obj['id']}' references zone '{obj['zone_id']}' which doesn't exist")
        if "triggers_hook" in obj and obj["triggers_hook"] not in hook_ids:
            errors.append({"path": f"objectives[{obj['id']}]", "message": f"triggers_hook '{obj['triggers_hook']}' not found in gm_hooks"})

    if errors:
        return json.dumps({"valid": False, "error_count": len(errors), "errors": errors, "warnings": warnings})

    return json.dumps({
        "valid": True,
        "scene_id": plan.get("id"),
        "scene_name": plan.get("name"),
        "zone_count": len(plan.get("zones", [])),
        "objective_count": len(plan.get("objectives", [])),
        "state_count": len(plan.get("narrative_states", [])),
        "hook_count": len(plan.get("gm_hooks", [])),
        "platforms": plan.get("platforms", []),
        "warnings": warnings,
        "message": "ScenePlan is valid and ready to save."
    })


@tool
def save_scene_plan(scene_plan_json: str) -> str:
    """Save a validated ScenePlan JSON to S3. Returns the S3 URI and a web-accessible summary.
    Only call this after validate_scene_plan confirms the plan is valid."""
    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    scene_id = plan.get("id") or str(uuid.uuid4())
    plan["id"] = scene_id

    s3_key = f"{S3_PREFIX}/{scene_id}/scene_plan.json"
    s3_uri = f"s3://{S3_BUCKET}/{s3_key}"

    try:
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(plan, indent=2).encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "scene-name": plan.get("name", "unnamed")[:255],
                "scene-type": plan.get("scene_type", "unknown"),
                "platforms": ",".join(plan.get("platforms", [])),
                "created-at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": f"S3 save failed: {e}"})

    return json.dumps({
        "status": "saved",
        "scene_id": scene_id,
        "scene_name": plan.get("name"),
        "s3_uri": s3_uri,
        "s3_key": s3_key,
        "platforms": plan.get("platforms", []),
        "zones": len(plan.get("zones", [])),
        "gm_hooks": [h["id"] for h in plan.get("gm_hooks", [])],
        "narrative_states": [s["id"] for s in plan.get("narrative_states", [])],
        "message": f"ScenePlan saved. Ready for UnrealLevelBuilder (VR) and/or WebPlatformAgent (web)."
    })


@tool
def place_narrative_hooks(scene_plan_json: str) -> str:
    """Review a ScenePlan and enrich its GM hooks with suggested effects based on zones, objectives,
    and narrative states. Returns an enriched scene plan JSON with more detailed hook effects.
    Use this to improve a draft plan before validating and saving."""
    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    scene_type = plan.get("scene_type", "exploration")
    zones = plan.get("zones", [])
    states = plan.get("narrative_states", [])
    hooks = plan.get("gm_hooks", [])
    objectives = plan.get("objectives", [])

    suggestions = []

    for hook in hooks:
        existing_effects = hook.get("effects", [])
        hook_id = hook["id"]

        # Find objectives that trigger this hook
        triggering_objectives = [o["description"] for o in objectives if o.get("triggers_hook") == hook_id]

        # Find state transitions that use this hook
        triggering_transitions = []
        for state in states:
            for t in state.get("transitions", []):
                if t.get("trigger_hook_id") == hook_id:
                    triggering_transitions.append(f"{state['id']} → {t['next_state_id']}")

        suggestions.append({
            "hook_id": hook_id,
            "hook_name": hook.get("name"),
            "current_effects": existing_effects,
            "triggered_by_objectives": triggering_objectives,
            "triggers_state_transitions": triggering_transitions,
            "suggestion": (
                f"Hook '{hook['name']}' fires when: {', '.join(triggering_objectives) or 'GM manual trigger'}. "
                f"{'Causes state transition: ' + ', '.join(triggering_transitions) + '. ' if triggering_transitions else ''}"
                f"Consider adding effects: atmosphere change, audio cue, VFX change, door/barrier state, participant notification."
            )
        })

    return json.dumps({
        "status": "ok",
        "scene_type": scene_type,
        "hook_count": len(hooks),
        "hook_analysis": suggestions,
        "note": "Review suggestions and update gm_hooks[].effects in your ScenePlan before saving."
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """EnvironmentDesigner: natural language → validated ScenePlan.json saved to S3."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[get_available_rewards, validate_scene_plan, save_scene_plan, place_narrative_hooks],
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
