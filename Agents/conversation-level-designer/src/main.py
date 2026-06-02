"""EnvironmentDesigner — natural language to ScenePlan conversion for Hypermage VR/Web.

Supports LARP scenes, cyberspace nodes, ritual spaces, and any experiential environment.
Outputs validated ScenePlan.json saved to S3, usable by both UE5 (VR) and Babylon.js (web).

Phase 7: Added get_available_assets() tool — queries DynamoDB asset catalogue so the
EnvironmentDesigner can reference commissioned/uploaded assets in ScenePlan asset_sources[].
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

MODEL_ID              = "eu.anthropic.claude-sonnet-4-6"
S3_BUCKET             = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")
S3_PREFIX             = "scene-plans"
ASSET_CATALOGUE_TABLE = os.environ.get("ASSET_CATALOGUE_TABLE", "hypermage-vr-asset-catalogue-dev")
AWS_REGION            = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

# Load schema and rewards catalog at startup (bundled alongside main.py in container)
_schema_path  = Path(__file__).parent / "ScenePlan.schema.json"
_catalog_path = Path(__file__).parent / "rewards_catalog.json"

with open(_schema_path) as f:
    SCENE_PLAN_SCHEMA = json.load(f)

with open(_catalog_path) as f:
    _catalog_data   = json.load(f)
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
- If the user mentions commissioned artwork or uploaded assets, call get_available_assets() and
  reference matching assets in asset_sources[] and zone asset_references[]

INTERACTIVE OBJECTS (zones[].interactables[]):
Every scene should populate interactables[] in appropriate zones. Four types are available:
- creature: AI enemy (patrol -> chase -> attack). Required fields: health, patrol_radius.
  Place in combat/exploration zones only - never in spawn zones.
  Use loot[] to drop artefacts on death. Creatures reset each session (persistent: false default).
  Use model_asset_id (from asset catalogue mesh assets) to replace the placeholder red cylinder with a real 3D model.
- machinery: Triggered mechanism (locked door, lever, puzzle device). Include trigger_radius.
  Use required_key_id to reference an artefact the player must carry to unlock it.
  Set persistent: true if the door should stay open across sessions.
  Use model_asset_id (from asset catalogue mesh assets) to replace the placeholder grey box with a real 3D model.
- artefact: Collectible item. Include artefact_id (from asset catalogue when available).
  Use grants_ability if collecting it powers up the player.
  Set persistent: true if collecting it once should be remembered (e.g. a boss key).
  artefact_id serves as the visual model ID for artefacts — the browser will load it as a 3D model if it is a glTF/glb asset in the catalogue.
- environmental: Scripted world event (collapsing bridge, gas trap, lightning strike).
  Include trigger_radius and a rich behaviour description. One-shot by default.
  Use model_asset_id (from asset catalogue mesh assets) to replace the placeholder orange disc with a real 3D model.

Rules for interactables:
- All gameplay is PvE - objects react to players, never player vs player
- Object IDs must be unique across the ENTIRE scene (prefix with zone id, e.g. "vault_guardian_1")
- audio_profile is mandatory - it feeds directly into the audio generation pipeline
- Position each object within its zone's bounds (use zone center +/- offset within extents)
- A machinery required_key_id must reference an artefact id that exists somewhere in the scene
- loot artefact_ids must reference artefact interactables that exist in the scene

When given a description:
1. Call get_available_rewards() to know which reward IDs are valid
2. Call get_available_assets() to see commissioned/uploaded assets in the catalogue
3. Reason through the scene design -- zones, atmosphere, narrative arc, GM hooks, and interactables
4. Generate the complete ScenePlan JSON
   - Populate interactables[] for each zone appropriate to the scene type
   - Combat/exploration zones: creatures + artefacts as loot
   - Objective zones: machinery (locks/puzzles) + key artefacts in adjacent zones
   - Environmental zones: environmental interactables triggered by player proximity
   - If catalogue mesh assets match the scene theme, set model_asset_id (creature/machinery/environmental)
     or artefact_id (artefact type) to the matching assetId from get_available_assets()
5. Call validate_scene_plan(scene_plan_json) to check it
6. Fix any validation errors and re-validate
7. Call save_scene_plan(scene_plan_json) to persist to S3
8. Return the final ScenePlan JSON with the S3 URI"""


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_available_rewards() -> str:
    """Return all valid reward IDs from the rewards catalog.
    Always call this before assigning reward_id values to objectives."""
    rewards = [
        {"id": r["id"], "name": r["name"], "description": r["description"], "category": r["category"]}
        for r in _catalog_data.get("rewards", [])
    ]
    return json.dumps({
        "status": "ok",
        "count":  len(rewards),
        "rewards": rewards,
        "note":   "Only use reward IDs from this list in ScenePlan objectives.",
    })


@tool
def get_available_assets(asset_type: str = "", tag: str = "") -> str:
    """Query the DynamoDB asset catalogue for ready assets.
    Optional filters:
      asset_type: mesh | texture | audio | concept_art | animation | material
      tag:        free-text tag for partial name/tag match
    Returns ready assets with their S3 URIs for use in ScenePlan asset_sources[].
    Call this before designing zones so you know what commissioned assets are available."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table    = dynamodb.Table(ASSET_CATALOGUE_TABLE)

        if asset_type:
            resp = table.query(
                IndexName="AssetTypeIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("assetType").eq(asset_type),
            )
        else:
            resp = table.scan()

        items = [i for i in resp.get("Items", []) if i.get("status") == "ready"]

        if tag:
            tag_lower = tag.lower()
            items = [
                i for i in items
                if any(tag_lower in t.lower() for t in i.get("tags", []))
                or tag_lower in i.get("assetName", "").lower()
            ]

        # Return a clean summary suitable for prompt context
        assets = []
        for item in items:
            outputs = item.get("outputs", {})
            assets.append({
                "assetId":   item.get("assetId"),
                "assetName": item.get("assetName", item.get("filename", "unnamed")),
                "assetType": item.get("assetType"),
                "tier":      item.get("tier"),
                "tags":      item.get("tags", []),
                "s3Uri":     item.get("s3Uri") or outputs.get("glb") or outputs.get("webp") or "",
                "outputs":   outputs,
                "provenance": {
                    "origin":  item.get("provenance", {}).get("origin"),
                    "license": item.get("provenance", {}).get("license"),
                },
            })

        return json.dumps({
            "status": "ok",
            "count":  len(assets),
            "assets": assets,
            "note":   (
                "Use s3Uri in asset_sources[].s3_uri. "
                "Reference assetId in zone asset_references[] to place in specific zones."
            ),
        }, default=str)

    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc), "assets": []})


@tool
def validate_scene_plan(scene_plan_json: str) -> str:
    """Validate a ScenePlan JSON string against the ScenePlan schema.
    Returns validation errors or confirms validity. Fix all errors before calling save_scene_plan."""
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
    warnings   = []
    state_ids  = {s["id"] for s in plan.get("narrative_states", [])}
    hook_ids   = {h["id"] for h in plan.get("gm_hooks", [])}
    zone_ids   = {z["id"] for z in plan.get("zones", [])}
    initial_states = [s for s in plan.get("narrative_states", []) if s.get("is_initial")]

    # Collect and validate interactables across all zones
    all_interactable_ids = []
    interactable_types   = {}
    spawn_zone_ids       = {z["id"] for z in plan.get("zones", []) if z.get("type") == "spawn"}

    for zone in plan.get("zones", []):
        zone_id = zone["id"]
        for obj in zone.get("interactables", []):
            obj_id   = obj.get("id", "")
            obj_type = obj.get("type", "")

            if obj_id in all_interactable_ids:
                errors.append({"path": f"zones[{zone_id}].interactables",
                               "message": f"Interactable id '{obj_id}' is not unique across the scene"})
            else:
                all_interactable_ids.append(obj_id)
                interactable_types[obj_id] = obj_type

            if obj_type == "creature" and zone_id in spawn_zone_ids:
                warnings.append(f"Creature '{obj_id}' is in spawn zone '{zone_id}' — move to combat/exploration zone")

            if "audio_profile" not in obj or not obj["audio_profile"]:
                warnings.append(f"Interactable '{obj_id}' has no audio_profile — audio pipeline will have no guidance")

    # Second pass: validate cross-references between interactables
    for zone in plan.get("zones", []):
        zone_id = zone["id"]
        for obj in zone.get("interactables", []):
            obj_id = obj.get("id", "")
            key_id = obj.get("required_key_id")
            if key_id:
                if key_id not in interactable_types:
                    errors.append({"path": f"zones[{zone_id}].interactables[{obj_id}]",
                                   "message": f"required_key_id '{key_id}' does not match any interactable id in the scene"})
                elif interactable_types[key_id] != "artefact":
                    errors.append({"path": f"zones[{zone_id}].interactables[{obj_id}]",
                                   "message": f"required_key_id '{key_id}' must reference an artefact (got '{interactable_types[key_id]}')"})
            for loot in obj.get("loot", []):
                loot_id = loot.get("artefact_id", "")
                if loot_id not in interactable_types:
                    errors.append({"path": f"zones[{zone_id}].interactables[{obj_id}].loot",
                                   "message": f"loot artefact_id '{loot_id}' does not match any interactable in the scene"})
                elif interactable_types.get(loot_id) != "artefact":
                    errors.append({"path": f"zones[{zone_id}].interactables[{obj_id}].loot",
                                   "message": f"loot artefact_id '{loot_id}' must be type artefact (got '{interactable_types.get(loot_id)}')"})


    if len(initial_states) != 1:
        errors.append({"path": "narrative_states",
                       "message": f"Exactly one narrative state must have is_initial=true, found {len(initial_states)}"})

    initial_state_ref = plan.get("narrative_context", {}).get("initial_state")
    if initial_state_ref and initial_state_ref not in state_ids:
        errors.append({"path": "narrative_context.initial_state",
                       "message": f"'{initial_state_ref}' not found in narrative_states"})

    for state in plan.get("narrative_states", []):
        for t in state.get("transitions", []):
            if t.get("trigger_hook_id") not in hook_ids:
                errors.append({"path": f"narrative_states[{state['id']}].transitions",
                               "message": f"hook '{t.get('trigger_hook_id')}' not found in gm_hooks"})
            if t.get("next_state_id") not in state_ids:
                errors.append({"path": f"narrative_states[{state['id']}].transitions",
                               "message": f"next_state '{t.get('next_state_id')}' not found in narrative_states"})

    for obj in plan.get("objectives", []):
        if "reward_id" in obj and obj["reward_id"] not in VALID_REWARD_IDS:
            warnings.append(f"objective '{obj['id']}' uses reward_id '{obj['reward_id']}' not in catalog")
        if "zone_id" in obj and obj["zone_id"] not in zone_ids:
            warnings.append(f"objective '{obj['id']}' references zone '{obj['zone_id']}' which doesn't exist")
        if "triggers_hook" in obj and obj["triggers_hook"] not in hook_ids:
            errors.append({"path": f"objectives[{obj['id']}]",
                           "message": f"triggers_hook '{obj['triggers_hook']}' not found in gm_hooks"})

    if errors:
        return json.dumps({"valid": False, "error_count": len(errors), "errors": errors, "warnings": warnings})

    interactable_count = sum(len(z.get("interactables", [])) for z in plan.get("zones", []))
    return json.dumps({
        "valid":              True,
        "scene_id":           plan.get("id"),
        "scene_name":         plan.get("name"),
        "zone_count":         len(plan.get("zones", [])),
        "interactable_count": interactable_count,
        "objective_count":    len(plan.get("objectives", [])),
        "state_count":        len(plan.get("narrative_states", [])),
        "hook_count":         len(plan.get("gm_hooks", [])),
        "asset_sources":      len(plan.get("asset_sources", [])),
        "platforms":          plan.get("platforms", []),
        "warnings":           warnings,
        "message":            "ScenePlan is valid and ready to save.",
    })


@tool
def save_scene_plan(scene_plan_json: str) -> str:
    """Save a validated ScenePlan JSON to S3. Returns the S3 URI and a web-accessible summary.
    Only call this after validate_scene_plan confirms the plan is valid."""
    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    scene_id   = plan.get("id") or str(uuid.uuid4())
    plan["id"] = scene_id
    s3_key     = f"{S3_PREFIX}/{scene_id}/scene_plan.json"
    s3_uri     = f"s3://{S3_BUCKET}/{s3_key}"

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(plan, indent=2).encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "scene-name":    plan.get("name", "unnamed")[:255],
                "scene-type":    plan.get("scene_type", "unknown"),
                "platforms":     ",".join(plan.get("platforms", [])),
                "created-at":    datetime.now(timezone.utc).isoformat(),
                "asset-sources": str(len(plan.get("asset_sources", []))),
            }
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": f"S3 save failed: {e}"})

    interactable_count = sum(len(z.get("interactables", [])) for z in plan.get("zones", []))
    return json.dumps({
        "status":             "saved",
        "scene_id":           scene_id,
        "scene_name":         plan.get("name"),
        "s3_uri":             s3_uri,
        "s3_key":             s3_key,
        "platforms":          plan.get("platforms", []),
        "zones":              len(plan.get("zones", [])),
        "interactable_count": interactable_count,
        "asset_sources":      len(plan.get("asset_sources", [])),
        "gm_hooks":           [h["id"] for h in plan.get("gm_hooks", [])],
        "narrative_states":   [s["id"] for s in plan.get("narrative_states", [])],
        "message":            "ScenePlan saved. Ready for UnrealLevelBuilder (VR) and/or WebPlatformAgent (web).",
    })


@tool
def place_narrative_hooks(scene_plan_json: str) -> str:
    """Review a ScenePlan and enrich its GM hooks with suggested effects based on zones, objectives,
    and narrative states. Returns hook analysis with suggestions.
    Use this to improve a draft plan before validating and saving."""
    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    hooks      = plan.get("gm_hooks", [])
    states     = plan.get("narrative_states", [])
    objectives = plan.get("objectives", [])
    suggestions = []

    for hook in hooks:
        hook_id = hook["id"]
        triggering_objectives  = [o["description"] for o in objectives if o.get("triggers_hook") == hook_id]
        triggering_transitions = [
            f"{s['id']} → {t['next_state_id']}"
            for s in states for t in s.get("transitions", [])
            if t.get("trigger_hook_id") == hook_id
        ]
        suggestions.append({
            "hook_id":                   hook_id,
            "hook_name":                 hook.get("name"),
            "current_effects":           hook.get("effects", []),
            "triggered_by_objectives":   triggering_objectives,
            "triggers_state_transitions": triggering_transitions,
            "suggestion": (
                f"Hook '{hook['name']}' fires when: {', '.join(triggering_objectives) or 'GM manual trigger'}. "
                + (f"Causes state transition: {', '.join(triggering_transitions)}. " if triggering_transitions else "")
                + "Consider adding effects: atmosphere change, audio cue, VFX change, door/barrier state, participant notification."
            ),
        })

    return json.dumps({
        "status":      "ok",
        "scene_type":  plan.get("scene_type", "exploration"),
        "hook_count":  len(hooks),
        "hook_analysis": suggestions,
        "note":        "Review suggestions and update gm_hooks[].effects in your ScenePlan before saving.",
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """EnvironmentDesigner: natural language → validated ScenePlan.json saved to S3."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[get_available_rewards, get_available_assets,
               validate_scene_plan, save_scene_plan, place_narrative_hooks],
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
