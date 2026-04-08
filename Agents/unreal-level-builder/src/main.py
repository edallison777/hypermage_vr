"""UnrealLevelBuilderAgent — LevelPlan / ScenePlan → live UE5 editor via UnrealBridge.

Phase 9: Real HTTP tools that call the UnrealBridge FastAPI service running on the dev PC.
  - get_bridge_status:      GET  {bridge}/health   — checks UE5 reachability
  - spawn_actor:            POST {bridge}/actor/create
  - set_actor_property:     POST {bridge}/actor/set-property
  - run_console_command:    POST {bridge}/console
  - save_level:             POST {bridge}/level/save
  - build_scene_from_plan:  POST {bridge}/scene-plan/build — full ScenePlan → blockout geometry

Bridge URL read from SSM /hypermage/unreal-bridge-url.
All tools skip gracefully (status='skipped') when the bridge is not configured or reachable.

To activate:
  1. Open UE5 with Remote Control plugin enabled
  2. Run scripts/unreal-bridge/start.sh --ngrok on the dev PC
  3. The start script auto-updates SSM with the ngrok URL
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID          = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION        = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
BRIDGE_URL_SSM    = os.environ.get("BRIDGE_URL_SSM", "/hypermage/unreal-bridge-url")

ssm = boto3.client("ssm", region_name=AWS_REGION)
_bridge_url_cache: str | None = None


def _get_bridge_url() -> str | None:
    """Read the UnrealBridge URL from SSM. Returns None if absent or NOT_SET."""
    global _bridge_url_cache
    if _bridge_url_cache is not None:
        return _bridge_url_cache
    try:
        resp  = ssm.get_parameter(Name=BRIDGE_URL_SSM)
        value = resp["Parameter"]["Value"]
        result = None if value in ("NOT_SET", "", "PLACEHOLDER") else value.rstrip("/")
    except Exception:
        result = None
    _bridge_url_cache = result
    return result


def _bridge_post(path: str, body: dict) -> dict:
    """POST to the UnrealBridge. Raises on HTTP error."""
    url   = f"{_get_bridge_url()}{path}"
    data  = json.dumps(body).encode()
    req   = urllib.request.Request(url, data=data, method="POST",
                                   headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _bridge_get(path: str) -> dict:
    """GET from the UnrealBridge."""
    url = f"{_get_bridge_url()}{path}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def _skip(reason: str) -> str:
    return json.dumps({"status": "skipped", "note": reason})


SYSTEM_PROMPT = """You are the UnrealLevelBuilderAgent for Hypermage — responsible for
converting ScenePlan and LevelPlan specifications into live Unreal Engine 5 levels.

You communicate with the dev PC's UnrealBridge service (a FastAPI wrapper for the UE5
Remote Control HTTP API). The bridge URL is stored in SSM and populated when the dev
PC runs start.sh --ngrok.

Your responsibilities:
1. Check bridge availability with get_bridge_status() before doing work
2. Build full scenes from ScenePlan JSON using build_scene_from_plan()
   — this spawns colour-coded zone blockouts + PlayerStart actors
3. Full ScenePlan → UE5 map conversion using convert_sceneplan_to_map()
   — zones + spawns + atmosphere + asset_sources + gm_hook TriggerVolumes
4. Apply atmosphere/lighting standalone using apply_atmosphere(lighting_mood)
5. Spawn individual actors for prototyping with spawn_actor()
6. Set mesh/material properties on actors with set_actor_property()
7. Run UE5 console commands with run_console_command()
8. Save the level after changes with save_level()

If the bridge is not configured (UE5 not running / ngrok not set):
  — report the status='skipped' response and advise the user to start the bridge

Zone blockout colour convention (to apply manually or via Blueprint after spawning):
  exploration=white  ritual=purple  social=yellow  sanctuary=green
  cyberspace=cyan    combat=red     objective=blue  spawn=orange  transition=grey

UE5 coordinate system: Z-up, centimetres (100 UU = 1 metre).
Always save_level() after a build to persist changes."""


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_bridge_status() -> str:
    """Check if the UnrealBridge is reachable and whether UE5 is responding.
    Call this first before any editor operations.
    Returns {status, ue5_reachable, bridge_url} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("UnrealBridge URL not set in SSM. "
                     "Run scripts/unreal-bridge/start.sh --ngrok on the dev PC.")
    try:
        result = _bridge_get("/health")
        return json.dumps({
            "status":       "ok",
            "bridge_url":   url,
            "ue5_reachable": result.get("ue5_reachable", False),
            "message":      "Bridge reachable" + (" — UE5 responding" if result.get("ue5_reachable") else " — UE5 NOT responding (open UE5 and enable Remote Control)"),
        })
    except urllib.error.HTTPError as exc:
        return json.dumps({"status": "error", "bridge_url": url, "error": f"HTTP {exc.code}"})
    except Exception as exc:
        return json.dumps({"status": "error", "bridge_url": url, "error": str(exc)})


@tool
def spawn_actor(actor_class: str, x: float, y: float, z: float,
                label: str = "", yaw: float = 0.0,
                scale_x: float = 1.0, scale_y: float = 1.0, scale_z: float = 1.0) -> str:
    """Spawn an actor in the currently open UE5 level.
    actor_class: UE5 class path, e.g. '/Script/Engine.StaticMeshActor' or '/Script/Engine.PlayerStart'
    x, y, z: world position in Unreal units (cm)
    label: name shown in the Outliner
    Returns {status, actor_path, label} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured.")
    try:
        result = _bridge_post("/actor/create", {
            "actor_class": actor_class,
            "label": label, "x": x, "y": y, "z": z,
            "yaw": yaw, "scale_x": scale_x, "scale_y": scale_y, "scale_z": scale_z,
        })
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def set_actor_property(actor_path: str, property_name: str, value: str) -> str:
    """Set a property on an actor by its UE5 object path.
    Common uses:
      property_name='StaticMesh', value='/Engine/BasicShapes/Cube.Cube'
      property_name='OverrideMaterials', value='/Game/Materials/M_Blockout_Red.M_Blockout_Red'
    Returns {status, actor_path, property} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured.")
    try:
        result = _bridge_post("/actor/set-property", {
            "actor_path": actor_path,
            "property_name": property_name,
            "value": value,
        })
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def run_console_command(command: str) -> str:
    """Execute a UE5 editor console command.
    Examples: 'stat fps', 'r.SetRes 1920x1080', 'obj list class=StaticMeshActor'
    Returns {status, command} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured.")
    try:
        result = _bridge_post("/console", {"command": command})
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def save_level() -> str:
    """Save the currently open UE5 level. Always call after spawning actors.
    Returns {status, message} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured.")
    try:
        result = _bridge_post("/level/save", {})
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def build_scene_from_plan(scene_plan_json: str, map_name: str = "NewMap") -> str:
    """Build a full scene in UE5 from a ScenePlan JSON.
    Spawns colour-coded blockout cube actors for each zone at the zone's
    bounds.center position, scaled to the zone's bounds.extents.
    Also places PlayerStart actors at each participant_spawn.
    Saves the level automatically on completion.
    Returns {status, actors_spawned, actors, errors} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured. Run scripts/unreal-bridge/start.sh --ngrok.")
    try:
        # Validate JSON first
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"status": "error", "error": f"Invalid ScenePlan JSON: {exc}"})

    try:
        result = _bridge_post("/scene-plan/build", {
            "scene_plan_json": scene_plan_json,
            "map_name": map_name,
        })
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def generate_blockout_geometry(zones: str) -> str:
    """Generate Unreal blockout geometry specification for zones from a JSON zones array.
    Returns actor spawn instructions for each zone — use spawn_actor() to execute them,
    or build_scene_from_plan() to process a full ScenePlan at once."""
    try:
        zone_list = json.loads(zones)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "error": "Invalid zones JSON"})

    TYPE_COLOR = {
        "exploration": "white",   "ritual":     "purple", "social":     "yellow",
        "sanctuary":   "green",   "cyberspace": "cyan",   "narrative":  "grey",
        "combat":      "red",     "objective":  "blue",   "spawn":      "orange",
        "transition":  "grey",
    }
    instructions = []
    for z in zone_list:
        b  = z.get("bounds", {})
        c  = b.get("center", {"x": 0, "y": 0, "z": 0})
        e  = b.get("extents", {"x": 100, "y": 100, "z": 100})
        zt = z.get("type", "exploration")
        instructions.append({
            "zone_id":    z.get("id"),
            "zone_name":  z.get("name"),
            "actor_class": "/Script/Engine.StaticMeshActor",
            "mesh":       "/Engine/BasicShapes/Cube.Cube",
            "label":      f"Zone_{z.get('name', z.get('id', ''))[:24]}",
            "position":   c,
            "scale":      {"x": e["x"]/50, "y": e["y"]/50, "z": e["z"]/50},
            "color_hint": TYPE_COLOR.get(zt, "white"),
        })
    return json.dumps({
        "status":        "ok",
        "instructions":  instructions,
        "note": "Call spawn_actor() for each instruction, or use build_scene_from_plan() for a full ScenePlan.",
    })


@tool
def convert_levelplan_to_map(level_plan: str, map_name: str) -> str:
    """Convert a LevelPlan.json to a UE5 map via the UnrealBridge.
    Delegates to build_scene_from_plan for ScenePlan-format plans, or returns
    spawn instructions for LevelPlan-format plans."""
    try:
        plan = json.loads(level_plan)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "error": "Invalid LevelPlan JSON"})

    # If it looks like a ScenePlan (has 'zones' + 'gm_hooks'), use build_scene_from_plan
    if "zones" in plan and "gm_hooks" in plan:
        return build_scene_from_plan(level_plan, map_name)

    # Legacy LevelPlan format — return instructions
    return json.dumps({
        "status":   "ok",
        "map_name": map_name,
        "message":  "LevelPlan parsed. Use build_scene_from_plan() with a ScenePlan for live UE5 placement.",
        "zones":    len(plan.get("zones", [])),
        "spawns":   len(plan.get("playerSpawns", [])),
    })


@tool
def apply_atmosphere(lighting_mood: str) -> str:
    """Apply atmosphere/lighting commands to the currently open UE5 level.
    Standalone tool — applies atmosphere without rebuilding geometry.

    lighting_mood examples: 'neon cyber', 'dark dramatic', 'golden warm', 'cool moonlit'

    Returns {status, lighting_mood, commands_run} JSON."""
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured. Run scripts/unreal-bridge/start.sh --ngrok.")

    mood   = lighting_mood.lower()
    errors = []
    ran    = []

    def _run(cmd: str) -> None:
        try:
            _bridge_post("/console", {"command": cmd})
            ran.append(cmd)
        except Exception as exc:
            errors.append({"cmd": cmd, "error": str(exc)})

    # Ambient occlusion — always
    _run("r.AmbientOcclusion.Intensity 1")

    if "neon" in mood or "cyber" in mood:
        _run("r.Atmosphere 0")
        _run("r.SkySphere.Intensity 0")
        _run("r.Fog 0")
        _run("r.AmbientOcclusion.Intensity 1.5")
        _run("r.BloomIntensity 2.0")
        _run("r.VignetteIntensity 0.8")
    elif "dark" in mood or "dramatic" in mood:
        _run("r.Atmosphere 1")
        _run("r.Fog 1")
        _run("r.VignetteIntensity 1.0")
        _run("r.BloomIntensity 1.5")
    elif "golden" in mood or "warm" in mood:
        _run("r.Atmosphere 1")
        _run("r.Fog 1")
        _run("r.BloomIntensity 1.2")
        _run("r.VignetteIntensity 0.3")
    elif "moonlit" in mood or "cool" in mood:
        _run("r.Atmosphere 1")
        _run("r.Fog 1")
        _run("r.BloomIntensity 0.8")
        _run("r.VignetteIntensity 0.5")
    elif "foggy" in mood or "grey" in mood:
        _run("r.Fog 1")
        _run("r.FogDensity 0.05")
        _run("r.BloomIntensity 0.5")
    else:
        # Default
        _run("r.Atmosphere 1")
        _run("r.BloomIntensity 1.0")
        _run("r.VignetteIntensity 0.3")

    return json.dumps({
        "status":        "ok" if not errors else "partial",
        "lighting_mood": lighting_mood,
        "commands_run":  len(ran),
        "commands":      ran,
        "errors":        errors,
    })


@tool
def convert_sceneplan_to_map(scene_plan_json: str, map_name: str = "GeneratedMap") -> str:
    """Full ScenePlan → UE5 map conversion.

    Beyond build_scene_from_plan (zones + spawns), this also:
    - Sets sky/atmosphere from ScenePlan atmosphere.lighting_mood
    - Places glTF/StaticMesh actors from asset_sources[]
    - Creates TriggerBox volumes for each gm_hook (with event tag = hook id)
    - Applies post-process console commands for atmosphere effects

    All steps skip gracefully if bridge not reachable.

    Returns {status, actors_spawned, atmosphere_applied, assets_placed, hooks_wired, errors} JSON.
    """
    url = _get_bridge_url()
    if not url:
        return _skip("Bridge not configured. Run scripts/unreal-bridge/start.sh --ngrok.")

    try:
        plan = json.loads(scene_plan_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"status": "error", "error": f"Invalid ScenePlan JSON: {exc}"})

    errors            = []
    actors_spawned    = 0
    assets_placed     = 0
    hooks_wired       = 0
    atmosphere_applied = False

    # ── Step 1: Zones + PlayerStarts (reuse /scene-plan/build) ────────────────
    try:
        result = _bridge_post("/scene-plan/build", {
            "scene_plan_json": scene_plan_json,
            "map_name":        map_name,
        })
        actors_spawned = result.get("actors_spawned", 0)
        if result.get("errors"):
            errors.extend(result["errors"])
    except Exception as exc:
        errors.append({"step": "zones_spawns", "error": str(exc)})

    # ── Step 2: Atmosphere ─────────────────────────────────────────────────────
    atmosphere    = plan.get("atmosphere", {})
    lighting_mood = atmosphere.get("lighting_mood", "")
    if lighting_mood:
        try:
            atm_result = json.loads(apply_atmosphere(lighting_mood))
            atmosphere_applied = atm_result.get("status") in ("ok", "partial")
            if atm_result.get("errors"):
                errors.extend(atm_result["errors"])
        except Exception as exc:
            errors.append({"step": "atmosphere", "error": str(exc)})

    # ── Step 3: Asset sources ──────────────────────────────────────────────────
    asset_sources = plan.get("asset_sources", [])
    for asset in asset_sources:
        asset_id = asset.get("asset_id", "")
        pos      = asset.get("position", {"x": 0, "y": 0, "z": 0})
        if not asset_id:
            continue
        label = f"Asset_{asset_id[:24]}"
        try:
            result = _bridge_post("/actor/create", {
                "actor_class": "/Script/Engine.StaticMeshActor",
                "label": label,
                "x": float(pos.get("x", 0)),
                "y": float(pos.get("y", 0)),
                "z": float(pos.get("z", 0)),
                "yaw": 0.0, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0,
            })
            actor_path = result.get("actor_path", "")
            # Attempt to set static mesh — conventional path /Game/Assets/{id}.{id}
            if actor_path:
                try:
                    _bridge_post("/actor/set-property", {
                        "actor_path":    actor_path,
                        "property_name": "StaticMesh",
                        "value":         f"/Game/Assets/{asset_id}.{asset_id}",
                    })
                except Exception:
                    pass  # mesh assignment is best-effort
            assets_placed += 1
        except Exception as exc:
            errors.append({"step": "asset_source", "asset_id": asset_id, "error": str(exc)})

    # ── Step 4: GM hook TriggerVolumes ─────────────────────────────────────────
    # Place TriggerVolume at center of first zone (or origin)
    zones        = plan.get("zones", [])
    first_center = {"x": 0, "y": 0, "z": 0}
    if zones:
        b = zones[0].get("bounds", {})
        first_center = b.get("center", first_center)

    for hook in plan.get("gm_hooks", []):
        hook_id   = hook.get("id", "")
        hook_name = hook.get("name", hook_id)
        if not hook_id:
            continue
        label = f"Hook_{hook_id[:28]}"
        try:
            result = _bridge_post("/actor/create", {
                "actor_class": "/Script/Engine.TriggerVolume",
                "label": label,
                "x": float(first_center.get("x", 0)),
                "y": float(first_center.get("y", 0)),
                "z": float(first_center.get("z", 100)),
                "yaw": 0.0, "scale_x": 2.0, "scale_y": 2.0, "scale_z": 2.0,
            })
            actor_path = result.get("actor_path", "")
            if actor_path:
                try:
                    _bridge_post("/actor/set-property", {
                        "actor_path":    actor_path,
                        "property_name": "Tags",
                        "value":         [hook_id],
                    })
                except Exception:
                    pass
            hooks_wired += 1
        except Exception as exc:
            errors.append({"step": "gm_hook", "hook_id": hook_id, "error": str(exc)})

    # ── Step 5: Save level ─────────────────────────────────────────────────────
    try:
        _bridge_post("/level/save", {})
    except Exception as exc:
        errors.append({"step": "save", "error": str(exc)})

    return json.dumps({
        "status":             "ok" if not errors else "partial",
        "map_name":           map_name,
        "scene_name":         plan.get("name", ""),
        "actors_spawned":     actors_spawned,
        "atmosphere_applied": atmosphere_applied,
        "assets_placed":      assets_placed,
        "hooks_wired":        hooks_wired,
        "errors":             errors,
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """UnrealLevelBuilderAgent: LevelPlan/ScenePlan → live UE5 editor via UnrealBridge."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[
            get_bridge_status, spawn_actor, set_actor_property,
            run_console_command, save_level, build_scene_from_plan,
            generate_blockout_geometry, convert_levelplan_to_map,
            convert_sceneplan_to_map, apply_atmosphere,
        ],
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
