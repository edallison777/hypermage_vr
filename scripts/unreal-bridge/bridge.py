"""
UnrealBridge — FastAPI service running on the dev PC.
Wraps the UE5 Remote Control HTTP API (port 30010) with a clean REST interface
so AgentCore agents can manipulate a live UE5 editor over the internet.

Prerequisites:
  1. UE5 open with a map loaded
  2. Remote Control Plugin enabled (Edit → Plugins → "Remote Control")
  3. DefaultEngine.ini contains:
       [/Script/RemoteControl.RemoteControlSettings]
       bIsRemoteControlHttpServerEnabled=True
       RemoteControlHttpServerPort=30010

Start:
  pip install fastapi uvicorn httpx
  python bridge.py                     # localhost:8765
  python bridge.py --port 8765 --host 0.0.0.0

For agents to reach it, expose via ngrok:
  ngrok http 8765
  # copy the https://*.ngrok.io URL into SSM:
  aws ssm put-parameter --name /hypermage/unreal-bridge-url \\
      --value https://YOUR.ngrok.io --type String --overwrite --region eu-west-1
"""

import argparse
import json
import logging
import os
import subprocess
import tempfile
import textwrap

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("unreal-bridge")

UE5_RC_URL   = "http://localhost:30010"
UE_CMD       = r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
UPROJECT     = r"C:\Users\j_e_a\OneDrive\Projects\Hypermage\Hypermage_VR\UnrealProject\HyperMageVR.uproject"

app = FastAPI(title="UnrealBridge", version="2.0.0",
              description="FastAPI wrapper for UE5 Remote Control — Phase 20")


# ── Pydantic models ───────────────────────────────────────────────────────────

class SpawnActorRequest(BaseModel):
    actor_class: str = "/Script/Engine.StaticMeshActor"
    label:       str = ""
    x:     float = 0.0
    y:     float = 0.0
    z:     float = 0.0
    pitch: float = 0.0
    yaw:   float = 0.0
    roll:  float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_z: float = 1.0


class SetPropertyRequest(BaseModel):
    actor_path:    str
    property_name: str
    value:         str | int | float | dict


class ConsoleCommandRequest(BaseModel):
    command: str


class NewLevelRequest(BaseModel):
    asset_path: str = "/Game/Maps/HMVRArena"


class ScenePlanRequest(BaseModel):
    scene_plan_json: str
    map_name:        str = "NewMap"


class ScenePlanFullRequest(BaseModel):
    scene_plan_json: str
    map_name:        str = "GeneratedMap"


class BuildArenaRequest(BaseModel):
    scene_plan_json: str
    map_name:        str = "HMVRArena"
    room_margin:     float = 500.0   # extra cm around zone extents


# ── UE5 Remote Control helpers ────────────────────────────────────────────────

async def rc_call(object_path: str, function_name: str,
                  parameters: dict | None = None,
                  generate_transaction: bool = True) -> dict:
    """Call a function on a UObject via UE5 Remote Control."""
    payload: dict = {
        "objectPath":           object_path,
        "functionName":         function_name,
        "generateTransaction":  generate_transaction,
    }
    if parameters:
        payload["parameters"] = parameters

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.put(f"{UE5_RC_URL}/remote/object/call",
                                json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


async def rc_set_property(object_path: str, property_name: str, value) -> dict:
    """Set a property on a UObject via UE5 Remote Control."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.put(
            f"{UE5_RC_URL}/remote/object/property",
            json={
                "objectPath":    object_path,
                "access":        "WRITE_ACCESS",
                "propertyValue": {property_name: value},
            }
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}


async def ue5_reachable() -> bool:
    """Return True if the UE5 Remote Control HTTP server is up."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{UE5_RC_URL}/remote/info")
            return resp.status_code < 500
    except Exception:
        return False


async def _spawn_actor(actor_class: str, label: str,
                       x: float, y: float, z: float,
                       scale_x: float = 1.0, scale_y: float = 1.0, scale_z: float = 1.0,
                       yaw: float = 0.0) -> str:
    """Spawn an actor and return its object path."""
    result = await rc_call(
        "/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
        "SpawnActorFromObject",
        {
            "ObjectToUse": actor_class,
            "Location":    {"X": x, "Y": y, "Z": z},
            "Rotation":    {"Roll": 0.0, "Pitch": 0.0, "Yaw": yaw},
            "Transient":   False,
        },
    )
    actor_path = result.get("ReturnValue", "")
    if actor_path and label:
        try:
            await rc_call(actor_path, "SetActorLabel", {"NewActorLabel": label})
        except Exception:
            pass
    if actor_path and (scale_x != 1.0 or scale_y != 1.0 or scale_z != 1.0):
        try:
            await rc_call(actor_path, "SetActorScale3D",
                          {"NewScale3D": {"X": scale_x, "Y": scale_y, "Z": scale_z}})
        except Exception:
            pass
    return actor_path


# ── Arena-building helpers ────────────────────────────────────────────────────

# Cube BasicShape is 100 × 100 × 100 cm at scale (1,1,1).
# Scale multiplier = desired_cm / 100.

def _cube_scale(cm: float) -> float:
    return max(cm / 100.0, 0.05)


def _compute_arena_bounds(plan: dict, margin: float) -> dict:
    """Derive arena dimensions from zone extents + margin."""
    min_x = min_y =  1e9
    max_x = max_y = -1e9
    max_z = 0.0
    for zone in plan.get("zones", []):
        b  = zone.get("bounds", {})
        c  = b.get("center",  {})
        e  = b.get("extents", {})
        cx = float(c.get("x", 0));  cy = float(c.get("y", 0))
        ex = float(e.get("x", 500)); ey = float(e.get("y", 500))
        ez = float(e.get("z", 300))
        min_x = min(min_x, cx - ex); max_x = max(max_x, cx + ex)
        min_y = min(min_y, cy - ey); max_y = max(max_y, cy + ey)
        max_z = max(max_z, ez)
    if min_x == 1e9:  # no zones — use sensible default
        min_x, min_y, max_x, max_y, max_z = -1500, -1500, 1500, 1500, 400
    min_x -= margin; min_y -= margin
    max_x += margin; max_y += margin
    height = max(max_z + margin, 500.0)
    return {
        "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
        "cx":  (min_x + max_x) / 2,
        "cy":  (min_y + max_y) / 2,
        "width":  max_x - min_x,
        "depth":  max_y - min_y,
        "height": height,
    }


async def _spawn_room_geometry(b: dict, spawned: list, errors: list) -> None:
    """Spawn floor + 4 walls + ceiling + DirectionalLight + SkyLight."""
    cx, cy   = b["cx"], b["cy"]
    w, d, h  = b["width"], b["depth"], b["height"]
    wall_t   = 30.0  # cm wall thickness

    room_pieces = [
        # label,     x,           y,           z,       sx,           sy,           sz
        ("Floor",   cx,          cy,           -10,     _cube_scale(w), _cube_scale(d), _cube_scale(20)),
        ("Ceiling", cx,          cy,           h+10,    _cube_scale(w), _cube_scale(d), _cube_scale(20)),
        ("Wall_N",  cx,          cy+d/2+wall_t/2, h/2, _cube_scale(w+wall_t*2), _cube_scale(wall_t), _cube_scale(h)),
        ("Wall_S",  cx,          cy-d/2-wall_t/2, h/2, _cube_scale(w+wall_t*2), _cube_scale(wall_t), _cube_scale(h)),
        ("Wall_E",  cx+w/2+wall_t/2, cy,      h/2,     _cube_scale(wall_t), _cube_scale(d), _cube_scale(h)),
        ("Wall_W",  cx-w/2-wall_t/2, cy,      h/2,     _cube_scale(wall_t), _cube_scale(d), _cube_scale(h)),
    ]

    for label, x, y, z, sx, sy, sz in room_pieces:
        try:
            actor_path = await _spawn_actor(
                "/Script/Engine.StaticMeshActor", f"Room_{label}",
                x, y, z, sx, sy, sz,
            )
            if actor_path:
                try:
                    await rc_set_property(actor_path, "StaticMesh",
                                          "/Engine/BasicShapes/Cube.Cube")
                except Exception:
                    pass
            spawned.append({"type": "room_geometry", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "room_geometry", "label": label, "error": str(exc)})

    # Skip DirectionalLight — default empty level already provides one.

    # Sky light for ambient fill
    try:
        sky_path = await _spawn_actor(
            "/Script/Engine.SkyLight", "SkyLight",
            cx, cy, h + 200,
        )
        spawned.append({"type": "lighting", "label": "SkyLight", "actor_path": sky_path})
    except Exception as exc:
        errors.append({"type": "lighting", "label": "SkyLight", "error": str(exc)})


# ── Interactable spawning ─────────────────────────────────────────────────────

# Maps ScenePlan interactable types to UE5 C++ actor class paths.
INTERACTABLE_CLASS = {
    "creature":      "/Script/HyperMageVR.HMVRCreature",
    "machinery":     "/Script/HyperMageVR.HMVRMachinery",
    "artefact":      "/Script/HyperMageVR.HMVRArtifact",
    "environmental": "/Script/HyperMageVR.HMVREnvironmental",
}


async def _set_interactable_props(actor_path: str, obj: dict, obj_type: str) -> None:
    """Set type-specific UPROPERTY values on a freshly spawned interactable."""
    props: dict[str, object] = {}

    if obj_type == "artefact":
        if obj.get("artefact_id"):
            props["ArtifactId"] = obj["artefact_id"]
        if obj.get("grants_ability"):
            props["bGrantsAbility"] = True
            props["AbilityId"]      = obj["grants_ability"]

    elif obj_type == "machinery":
        if obj.get("required_key_id"):
            props["bRequiresKey"]  = True
            props["RequiredKeyId"] = obj["required_key_id"]
        if obj.get("unlock_time") is not None:
            props["TriggerDelay"] = float(obj["unlock_time"])

    elif obj_type == "creature":
        if obj.get("health") is not None:
            props["MaxHealth"] = float(obj["health"])
        if obj.get("patrol_radius") is not None:
            props["DetectionRadius"] = float(obj["patrol_radius"])
        if obj.get("attack_damage") is not None:
            props["AttackDamage"] = float(obj["attack_damage"])

    elif obj_type == "environmental":
        if obj.get("trigger_radius") is not None:
            props["TriggerRadius"] = float(obj["trigger_radius"])
        if obj.get("auto_trigger") is not None:
            props["bAutoTrigger"] = bool(obj["auto_trigger"])
        if obj.get("event_duration") is not None:
            props["EventSequenceDuration"] = float(obj["event_duration"])

    # Set object_id on the InteractableComponent for world-state persistence
    if obj.get("id"):
        try:
            await rc_set_property(
                f"{actor_path}.Interactable", "ObjectId", obj["id"]
            )
        except Exception:
            pass

    for prop, val in props.items():
        try:
            await rc_set_property(actor_path, prop, val)
        except Exception:
            pass


async def _spawn_interactables_for_zones(plan: dict, spawned: list, errors: list) -> int:
    """Spawn all interactable actors from every zone's interactables[] array."""
    count = 0
    for zone in plan.get("zones", []):
        for obj in zone.get("interactables", []):
            obj_type = obj.get("type", "").lower()
            actor_class = INTERACTABLE_CLASS.get(obj_type)
            if not actor_class:
                errors.append({"type": "interactable", "id": obj.get("id"),
                                "error": f"Unknown interactable type: {obj_type}"})
                continue

            pos   = obj.get("position", {})
            x     = float(pos.get("x", 0))
            y     = float(pos.get("y", 0))
            z     = float(pos.get("z", 100))
            label = f"{obj_type.capitalize()}_{obj.get('id', str(count))[:24]}"

            try:
                actor_path = await _spawn_actor(actor_class, label, x, y, z)
                if actor_path:
                    await _set_interactable_props(actor_path, obj, obj_type)
                spawned.append({
                    "type":       "interactable",
                    "subtype":    obj_type,
                    "label":      label,
                    "id":         obj.get("id"),
                    "actor_path": actor_path,
                })
                count += 1
                log.info(f"  spawned {obj_type} '{label}' at ({x},{y},{z})")
            except Exception as exc:
                errors.append({"type": "interactable", "label": label, "error": str(exc)})

    return count


# ── Core scene-plan build logic (shared by build-full and build-arena) ────────

async def _execute_scene_plan_build(plan: dict, spawned: list, errors: list) -> dict:
    """
    Zones + PlayerStarts + atmosphere + asset_sources + gm_hooks + interactables.
    Returns summary counts.
    """
    ZONE_TYPE_SUFFIX = {
        "exploration": "EX", "ritual": "RT", "social": "SO",
        "sanctuary": "SA", "cyberspace": "CS", "narrative": "NA",
        "combat": "CB", "objective": "OB", "spawn": "SP", "transition": "TR",
    }

    assets_placed   = 0
    hooks_wired     = 0
    atmosphere_cmds = []

    # 1. Zone blockouts
    for zone in plan.get("zones", []):
        bounds  = zone.get("bounds", {})
        center  = bounds.get("center",  {})
        extents = bounds.get("extents", {})
        suffix  = ZONE_TYPE_SUFFIX.get(zone.get("type", ""), "ZN")
        label   = f"{suffix}_{zone.get('name', zone.get('id', 'Zone'))[:24]}"
        try:
            actor_path = await _spawn_actor(
                "/Script/Engine.StaticMeshActor", label,
                float(center.get("x", 0)),
                float(center.get("y", 0)),
                float(center.get("z", 0)),
                max(float(extents.get("x", 100)) / 50.0, 0.1),
                max(float(extents.get("y", 100)) / 50.0, 0.1),
                max(float(extents.get("z", 100)) / 50.0, 0.1),
            )
            if actor_path:
                try:
                    await rc_set_property(actor_path, "StaticMesh",
                                          "/Engine/BasicShapes/Cube.Cube")
                except Exception:
                    pass
            spawned.append({"type": "zone", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "zone", "label": label, "error": str(exc)})

    # 2. PlayerStarts
    for i, spawn in enumerate(plan.get("participant_spawns", [])):
        pos   = spawn.get("position", {})
        rot   = spawn.get("rotation", {})
        label = f"PlayerStart_{i + 1}_{spawn.get('role', 'player')}"
        try:
            actor_path = await _spawn_actor(
                "/Script/Engine.PlayerStart", label,
                float(pos.get("x", 0)),
                float(pos.get("y", 0)),
                float(pos.get("z", 100)),
                yaw=float(rot.get("yaw", 0)),
            )
            spawned.append({"type": "player_start", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "player_start", "label": label, "error": str(exc)})

    # 3. Atmosphere console commands
    lighting_mood = plan.get("atmosphere", {}).get("lighting_mood", "").lower()
    if lighting_mood:
        if "neon" in lighting_mood or "cyber" in lighting_mood:
            atm_cmds = ["r.Atmosphere 0", "r.BloomIntensity 2.0",
                        "r.AmbientOcclusion.Intensity 1.5", "r.VignetteIntensity 0.8"]
        elif "dark" in lighting_mood or "dramatic" in lighting_mood:
            atm_cmds = ["r.Atmosphere 1", "r.BloomIntensity 1.5", "r.VignetteIntensity 1.0"]
        elif "golden" in lighting_mood or "warm" in lighting_mood:
            atm_cmds = ["r.Atmosphere 1", "r.BloomIntensity 1.2", "r.VignetteIntensity 0.3"]
        else:
            atm_cmds = ["r.Atmosphere 1", "r.BloomIntensity 1.0", "r.VignetteIntensity 0.3"]
        for cmd in atm_cmds:
            try:
                await rc_call("/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
                              "ExecuteConsoleCommand", {"Command": cmd},
                              generate_transaction=False)
                atmosphere_cmds.append(cmd)
            except Exception as exc:
                errors.append({"type": "atmosphere_cmd", "cmd": cmd, "error": str(exc)})

    # 4. Asset sources
    for asset in plan.get("asset_sources", []):
        asset_id = asset.get("asset_id", "")
        pos      = asset.get("position", {"x": 0, "y": 0, "z": 0})
        if not asset_id:
            continue
        label = f"Asset_{asset_id[:24]}"
        try:
            actor_path = await _spawn_actor(
                "/Script/Engine.StaticMeshActor", label,
                float(pos.get("x", 0)), float(pos.get("y", 0)), float(pos.get("z", 0)),
            )
            if actor_path:
                try:
                    await rc_set_property(actor_path, "StaticMesh",
                                          f"/Game/Assets/{asset_id}.{asset_id}")
                except Exception:
                    pass
            assets_placed += 1
            spawned.append({"type": "asset", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "asset", "asset_id": asset_id, "error": str(exc)})

    # 5. GM hook TriggerVolumes
    zones = plan.get("zones", [])
    first_center = {"x": 0, "y": 0, "z": 100}
    if zones:
        b = zones[0].get("bounds", {})
        first_center = b.get("center", first_center)
    for hook in plan.get("gm_hooks", []):
        hook_id = hook.get("id", "")
        if not hook_id:
            continue
        label = f"Hook_{hook_id[:28]}"
        try:
            actor_path = await _spawn_actor(
                "/Script/Engine.TriggerVolume", label,
                float(first_center.get("x", 0)),
                float(first_center.get("y", 0)),
                float(first_center.get("z", 100)),
                2.0, 2.0, 2.0,
            )
            if actor_path:
                try:
                    await rc_set_property(actor_path, "Tags", [hook_id])
                except Exception:
                    pass
            hooks_wired += 1
            spawned.append({"type": "hook_trigger", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "hook_trigger", "hook_id": hook_id, "error": str(exc)})

    # 6. Interactables (Phase 20)
    interactables_spawned = await _spawn_interactables_for_zones(plan, spawned, errors)

    return {
        "assets_placed":          assets_placed,
        "hooks_wired":            hooks_wired,
        "interactables_spawned":  interactables_spawned,
        "atmosphere_applied":     len(atmosphere_cmds) > 0,
        "atmosphere_mood":        lighting_mood,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Check bridge status and UE5 reachability."""
    ue5_up = await ue5_reachable()
    return {"status": "ok", "ue5_reachable": ue5_up, "ue5_rc_url": UE5_RC_URL}


@app.post("/level/new")
async def new_level(req: NewLevelRequest):
    """Save the current open level as the given asset path (NewLevel is blocked in UE5.3 RC)."""
    log.info(f"new_level (save-as) path={req.asset_path}")
    try:
        await rc_call(
            "/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
            "SaveCurrentLevel",
            generate_transaction=False,
        )
        return {"status": "ok", "note": "saved current level (NewLevel blocked remotely)", "asset_path": req.asset_path}
    except httpx.ConnectError:
        raise HTTPException(503, "UE5 Remote Control not reachable")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/actor/create")
async def create_actor(req: SpawnActorRequest):
    """Spawn an actor in the currently open UE5 level."""
    log.info(f"spawn_actor class={req.actor_class} label={req.label} pos=({req.x},{req.y},{req.z})")
    try:
        actor_path = await _spawn_actor(
            req.actor_class, req.label,
            req.x, req.y, req.z,
            req.scale_x, req.scale_y, req.scale_z,
            req.yaw,
        )
        return {"status": "ok", "actor_path": actor_path, "label": req.label}
    except httpx.ConnectError:
        raise HTTPException(503, "UE5 Remote Control not reachable — is UE5 open with Remote Control enabled?")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/actor/set-property")
async def set_property(req: SetPropertyRequest):
    """Set a property on an actor by its object path."""
    log.info(f"set_property path={req.actor_path} prop={req.property_name}")
    try:
        result = await rc_set_property(req.actor_path, req.property_name, req.value)
        return {"status": "ok", "actor_path": req.actor_path,
                "property": req.property_name, "result": result}
    except httpx.ConnectError:
        raise HTTPException(503, "UE5 not reachable")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/level/save")
async def save_level():
    """Save the currently open UE5 level."""
    log.info("save_level")
    try:
        await rc_call("/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
                      "SaveCurrentLevel", generate_transaction=False)
        return {"status": "ok", "message": "Level saved"}
    except httpx.ConnectError:
        raise HTTPException(503, "UE5 not reachable")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/console")
async def console_command(req: ConsoleCommandRequest):
    """Execute a UE5 console command."""
    log.info(f"console: {req.command}")
    try:
        await rc_call("/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
                      "ExecuteConsoleCommand",
                      {"Command": req.command},
                      generate_transaction=False)
        return {"status": "ok", "command": req.command}
    except httpx.ConnectError:
        raise HTTPException(503, "UE5 not reachable")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/scene-plan/build")
async def build_scene_from_plan(req: ScenePlanRequest):
    """Parse a ScenePlan JSON and spawn blockout geometry + PlayerStarts."""
    log.info(f"build_scene map={req.map_name}")
    try:
        plan = json.loads(req.scene_plan_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid ScenePlan JSON: {exc}")

    spawned: list = []
    errors:  list = []
    counts = await _execute_scene_plan_build(plan, spawned, errors)

    try:
        await rc_call("/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
                      "SaveCurrentLevel", generate_transaction=False)
    except Exception as exc:
        errors.append({"type": "save", "error": str(exc)})

    return {
        "status":      "ok" if not errors else "partial",
        "scene_name":  plan.get("name"),
        "actors":      spawned,
        "errors":      errors,
        **counts,
    }


@app.post("/scene-plan/build-full")
async def build_scene_full(req: ScenePlanFullRequest):
    """Full ScenePlan → UE5 map: zones + spawns + atmosphere + assets + hooks + interactables.
    Operates on the currently open level."""
    log.info(f"build_scene_full map={req.map_name}")
    try:
        plan = json.loads(req.scene_plan_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid ScenePlan JSON: {exc}")

    spawned: list = []
    errors:  list = []
    counts = await _execute_scene_plan_build(plan, spawned, errors)

    try:
        await rc_call("/Script/EditorScriptingUtilities.Default__EditorLevelLibrary",
                      "SaveCurrentLevel", generate_transaction=False)
    except Exception as exc:
        errors.append({"type": "save", "error": str(exc)})

    return {
        "status":         "ok" if not errors else "partial",
        "scene_name":     plan.get("name", ""),
        "map_name":       req.map_name,
        "actors_spawned": len([s for s in spawned if s["type"] in ("zone", "player_start")]),
        "actors":         spawned,
        "errors":         errors,
        **counts,
    }


def _run_ue_python(script: str) -> dict:
    """
    Write script to a temp file, run UnrealEditor-Cmd headlessly, return the
    JSON result the script writes to a well-known result path.
    Zero editor interaction required — editor does not need to be open.
    """
    result_path = os.path.join(tempfile.gettempdir(), "ue_bridge_result.json")
    # Inject result_path so script knows where to write
    full_script = f'_UE_RESULT_PATH = r"{result_path}"\n' + script

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(full_script)
        script_path = f.name

    try:
        proc = subprocess.run(
            [UE_CMD, UPROJECT,
             "-run=pythonscript", f"-script={script_path}",
             "-stdout", "-unattended", "-nopause", "-nosplash"],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        log.info(f"UE commandlet exit={proc.returncode}")
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as f:
                return json.load(f)
        # No result file — check for errors in output
        errors = [l for l in proc.stdout.splitlines() if "Error" in l and "Warning" not in l]
        return {"status": "error", "errors": errors[:10], "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"status": "error", "errors": ["UE commandlet timed out after 300s"]}
    finally:
        try: os.unlink(script_path)
        except Exception: pass
        try: os.unlink(result_path)
        except Exception: pass


@app.post("/scene-plan/build-arena")
async def build_arena(req: BuildArenaRequest):
    """
    Full pipeline via UE5 Python commandlet — zero editor interaction.
    Creates/loads the level, places room geometry + all scene content, saves.
    The editor does not need to be open.
    """
    log.info(f"build_arena map={req.map_name} (commandlet mode)")
    try:
        plan = json.loads(req.scene_plan_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid ScenePlan JSON: {exc}")

    plan_escaped = json.dumps(json.dumps(plan))  # double-encode for embedding in Python string

    script = textwrap.dedent(f"""
import unreal, json, traceback

PLAN       = json.loads({plan_escaped})
MAP_NAME   = {json.dumps(req.map_name)}
MARGIN     = {req.room_margin}
ASSET_PATH = f"/Game/{{MAP_NAME}}"

spawned = []
errors  = []

try:
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

    # ── 1. Load or create level ───────────────────────────────────────────────
    loaded = level_sub.load_level(ASSET_PATH)
    if not loaded:
        level_sub.new_level(ASSET_PATH)
        spawned.append({{"type": "level", "action": "created", "path": ASSET_PATH}})
    else:
        spawned.append({{"type": "level", "action": "loaded", "path": ASSET_PATH}})

    cube_mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")

    def spawn_cube(label, x, y, z, sx, sy, sz, yaw=0.0):
        loc = unreal.Vector(x, y, z)
        rot = unreal.Rotator(0, yaw, 0)
        a = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
        if a:
            a.set_actor_label(label)
            a.set_actor_scale3d(unreal.Vector(sx, sy, sz))
            a.static_mesh_component.set_static_mesh(cube_mesh)
        return a

    def cs(cm): return max(cm / 100.0, 0.05)

    # ── 2. Compute room bounds ────────────────────────────────────────────────
    min_x = min_y =  1e9
    max_x = max_y = -1e9
    max_z = 300.0
    for z in PLAN.get("zones", []):
        b  = z.get("bounds", {{}})
        c  = b.get("center",  {{}})
        e  = b.get("extents", {{}})
        cx_, cy_ = float(c.get("x", 0)), float(c.get("y", 0))
        ex_, ey_ = float(e.get("x", 500)), float(e.get("y", 500))
        ez_      = float(e.get("z", 300))
        min_x = min(min_x, cx_ - ex_); max_x = max(max_x, cx_ + ex_)
        min_y = min(min_y, cy_ - ey_); max_y = max(max_y, cy_ + ey_)
        max_z = max(max_z, ez_)
    if min_x == 1e9:
        min_x, min_y, max_x, max_y, max_z = -1500, -1500, 1500, 1500, 400
    min_x -= MARGIN; min_y -= MARGIN; max_x += MARGIN; max_y += MARGIN
    height = max_z + MARGIN
    rcx = (min_x + max_x) / 2;  rcy = (min_y + max_y) / 2
    w   = max_x - min_x;        d   = max_y - min_y
    wt  = 30.0

    # ── 3. Room geometry ──────────────────────────────────────────────────────
    pieces = [
        ("Room_Floor",   rcx, rcy, -10,          cs(w),       cs(d),  cs(20)),
        ("Room_Ceiling", rcx, rcy, height+10,     cs(w),       cs(d),  cs(20)),
        ("Room_Wall_N",  rcx, rcy+d/2+wt/2, height/2, cs(w+wt*2), cs(wt), cs(height)),
        ("Room_Wall_S",  rcx, rcy-d/2-wt/2, height/2, cs(w+wt*2), cs(wt), cs(height)),
        ("Room_Wall_E",  rcx+w/2+wt/2, rcy, height/2, cs(wt), cs(d), cs(height)),
        ("Room_Wall_W",  rcx-w/2-wt/2, rcy, height/2, cs(wt), cs(d), cs(height)),
    ]
    for label, x, y, z, sx, sy, sz in pieces:
        try:
            a = spawn_cube(label, x, y, z, sx, sy, sz)
            spawned.append({{"type": "room", "label": label, "ok": a is not None}})
        except Exception as exc:
            errors.append({{"type": "room", "label": label, "error": str(exc)}})

    # ── 4. Zone blockouts + PlayerStarts ─────────────────────────────────────
    zone_colours = {{"spawn": "SP", "ritual": "RT", "objective": "OB",
                    "combat": "CB", "exploration": "EX", "social": "SO",
                    "sanctuary": "SA", "hybrid": "HY"}}
    for zone in PLAN.get("zones", []):
        zid   = zone.get("id", "zone")
        ztype = zone.get("type", "zone")
        zname = zone.get("name", zid)
        b     = zone.get("bounds", {{}})
        c     = b.get("center",  {{}})
        e     = b.get("extents", {{}})
        prefix = zone_colours.get(ztype, "ZN")
        label  = f"{{prefix}}_{{zname}}"
        x, y, z_ = float(c.get("x", 0)), float(c.get("y", 0)), float(c.get("z", 0))
        ex, ey, ez = float(e.get("x", 500)), float(e.get("y", 500)), float(e.get("z", 200))
        try:
            a = spawn_cube(label, x, y, z_, cs(ex*2), cs(ey*2), cs(ez*2))
            spawned.append({{"type": "zone", "id": zid, "label": label, "ok": a is not None}})
        except Exception as exc:
            errors.append({{"type": "zone", "id": zid, "error": str(exc)}})

    for sp in PLAN.get("participant_spawns", []):
        sid = sp.get("spawn_id", "spawn")
        p   = sp.get("position", {{}})
        r   = sp.get("rotation", {{}})
        sx_, sy_, sz_ = float(p.get("x", 0)), float(p.get("y", 0)), float(p.get("z", 0))
        yaw_ = float(r.get("yaw", 0))
        try:
            loc_ = unreal.Vector(sx_, sy_, sz_)
            rot_ = unreal.Rotator(0, yaw_, 0)
            a = actor_sub.spawn_actor_from_class(unreal.PlayerStart, loc_, rot_)
            if a: a.set_actor_label(f"PlayerStart_{{sid}}")
            spawned.append({{"type": "player_start", "id": sid, "ok": a is not None}})
        except Exception as exc:
            errors.append({{"type": "player_start", "id": sid, "error": str(exc)}})

    # ── 5. Interactables ─────────────────────────────────────────────────────
    CLASS_MAP = {{
        "artefact":      "/Script/HyperMageVR.HMVRArtifact",
        "machinery":     "/Script/HyperMageVR.HMVRMachinery",
        "creature":      "/Script/HyperMageVR.HMVRCreature",
        "environmental": "/Script/HyperMageVR.HMVREnvironmental",
    }}
    for zone in PLAN.get("zones", []):
        for obj in zone.get("interactables", []):
            oid   = obj.get("id", "obj")
            otype = obj.get("type", "artefact")
            oname = obj.get("label", oid)
            pos   = obj.get("position", {{}})
            ox, oy, oz = float(pos.get("x", 0)), float(pos.get("y", 0)), float(pos.get("z", 0))
            cls_path = CLASS_MAP.get(otype)
            prefix   = otype[:4].upper()
            label    = f"{{prefix}}_{{oname}}"
            try:
                cls = unreal.load_class(None, cls_path) if cls_path else None
                if cls:
                    loc_ = unreal.Vector(ox, oy, oz)
                    rot_ = unreal.Rotator(0, 0, 0)
                    a = actor_sub.spawn_actor_from_class(cls, loc_, rot_)
                else:
                    a = spawn_cube(label, ox, oy, oz, 0.5, 0.5, 0.5)
                if a: a.set_actor_label(label)
                spawned.append({{"type": "interactable", "id": oid, "label": label, "ok": a is not None}})
            except Exception as exc:
                errors.append({{"type": "interactable", "id": oid, "error": str(exc)}})

    # ── 6. GM hook trigger volumes ────────────────────────────────────────────
    for i, hook in enumerate(PLAN.get("gm_hooks", [])):
        hid   = hook.get("id", f"hook_{{i}}")
        label = f"GMHOOK_{{hid}}"
        hx    = -5000.0
        hy    = 3000.0 + i * 400.0
        try:
            loc_ = unreal.Vector(hx, hy, 200)
            rot_ = unreal.Rotator(0, 0, 0)
            a = actor_sub.spawn_actor_from_class(unreal.TriggerVolume, loc_, rot_)
            if a: a.set_actor_label(label)
            spawned.append({{"type": "gm_hook", "id": hid, "ok": a is not None}})
        except Exception as exc:
            errors.append({{"type": "gm_hook", "id": hid, "error": str(exc)}})

    # ── 7. Save ───────────────────────────────────────────────────────────────
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    spawned.append({{"type": "save", "ok": True}})

except Exception as exc:
    errors.append({{"type": "fatal", "error": traceback.format_exc()}})

result = {{
    "status":   "ok" if not errors else "partial",
    "spawned":  spawned,
    "errors":   errors,
    "n_room":        sum(1 for s in spawned if s["type"] == "room"),
    "n_zones":       sum(1 for s in spawned if s["type"] == "zone"),
    "n_starts":      sum(1 for s in spawned if s["type"] == "player_start"),
    "n_interactables": sum(1 for s in spawned if s["type"] == "interactable"),
    "n_hooks":       sum(1 for s in spawned if s["type"] == "gm_hook"),
}}
with open(_UE_RESULT_PATH, "w", encoding="utf-8") as _f:
    json.dump(result, _f)
""")

    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_ue_python, script)

    if result.get("status") == "error":
        raise HTTPException(500, f"UE commandlet failed: {result.get('errors')}")

    return {
        "status":           result.get("status", "ok"),
        "level_asset_path": f"/Game/{req.map_name}",
        "scene_name":       plan.get("name", ""),
        "n_room":           result.get("n_room", 0),
        "n_zones":          result.get("n_zones", 0),
        "n_player_starts":  result.get("n_starts", 0),
        "n_interactables":  result.get("n_interactables", 0),
        "n_hooks":          result.get("n_hooks", 0),
        "spawned":          result.get("spawned", []),
        "errors":           result.get("errors", []),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"UnrealBridge starting on http://{args.host}:{args.port}")
    print(f"UE5 Remote Control expected at: {UE5_RC_URL}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
