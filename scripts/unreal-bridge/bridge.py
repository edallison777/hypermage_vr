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

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("unreal-bridge")

UE5_RC_URL = "http://localhost:30010"  # UE5 Remote Control HTTP API

app = FastAPI(title="UnrealBridge", version="1.0.0",
              description="FastAPI wrapper for UE5 Remote Control — Phase 9")


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


class ScenePlanRequest(BaseModel):
    scene_plan_json: str
    map_name:        str = "NewMap"


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Check bridge status and UE5 reachability."""
    ue5_up = await ue5_reachable()
    return {"status": "ok", "ue5_reachable": ue5_up, "ue5_rc_url": UE5_RC_URL}


@app.post("/actor/create")
async def create_actor(req: SpawnActorRequest):
    """Spawn an actor in the currently open UE5 level.
    Returns the spawned actor's object path."""
    log.info(f"spawn_actor class={req.actor_class} label={req.label} pos=({req.x},{req.y},{req.z})")
    try:
        result = await rc_call(
            "/Script/EditorScriptingUtilities.Default__EditorActorSubsystem",
            "SpawnActorFromClass",
            {
                "ActorClass": req.actor_class,
                "SpawnTransform": {
                    "Rotation":    {"X": req.pitch, "Y": req.yaw, "Z": req.roll, "W": 1.0},
                    "Translation": {"X": req.x,     "Y": req.y,   "Z": req.z},
                    "Scale3D":     {"X": req.scale_x, "Y": req.scale_y, "Z": req.scale_z},
                },
            },
        )
        actor_path = result.get("ActorObject", {}).get("ObjectPath", "")

        # Apply label if given
        if req.label and actor_path:
            try:
                await rc_call(actor_path, "SetActorLabel",
                               {"NewActorLabel": req.label})
            except Exception:
                pass  # label is best-effort

        log.info(f"  spawned → {actor_path}")
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
        await rc_call("/Script/UnrealEd.Default__EditorLevelLibrary",
                      "SaveCurrentLevel",
                      generate_transaction=False)
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
        await rc_call("/Script/UnrealEd.Default__EditorLevelLibrary",
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
    """Parse a ScenePlan JSON and spawn blockout geometry for each zone.
    Zones become colour-coded cube actors at the zone's bounds.center, scaled to bounds.extents.
    Also places PlayerStart actors at participant_spawns."""
    log.info(f"build_scene map={req.map_name}")

    try:
        plan = json.loads(req.scene_plan_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid ScenePlan JSON: {exc}")

    ZONE_TYPE_SUFFIX = {
        "exploration": "EX", "ritual": "RT", "social": "SO",
        "sanctuary": "SA", "cyberspace": "CS", "narrative": "NA",
        "combat": "CB", "objective": "OB", "spawn": "SP", "transition": "TR",
    }

    spawned = []
    errors  = []

    # 1. Blockout cubes for each zone
    for zone in plan.get("zones", []):
        bounds  = zone.get("bounds", {})
        center  = bounds.get("center", {})
        extents = bounds.get("extents", {})
        suffix  = ZONE_TYPE_SUFFIX.get(zone.get("type", ""), "ZN")
        label   = f"{suffix}_{zone.get('name', zone.get('id', 'Zone'))[:24]}"

        try:
            result = await rc_call(
                "/Script/EditorScriptingUtilities.Default__EditorActorSubsystem",
                "SpawnActorFromClass",
                {
                    "ActorClass": "/Script/Engine.StaticMeshActor",
                    "SpawnTransform": {
                        "Rotation":    {"X": 0, "Y": 0, "Z": 0, "W": 1},
                        "Translation": {
                            "X": float(center.get("x", 0)),
                            "Y": float(center.get("y", 0)),
                            "Z": float(center.get("z", 0)),
                        },
                        "Scale3D": {
                            "X": max(float(extents.get("x", 100)) / 50.0, 0.1),
                            "Y": max(float(extents.get("y", 100)) / 50.0, 0.1),
                            "Z": max(float(extents.get("z", 100)) / 50.0, 0.1),
                        },
                    },
                },
            )
            actor_path = result.get("ActorObject", {}).get("ObjectPath", "")
            if actor_path:
                # Set cube mesh and label
                try:
                    await rc_set_property(actor_path, "StaticMesh",
                                          "/Engine/BasicShapes/Cube.Cube")
                    await rc_call(actor_path, "SetActorLabel",
                                   {"NewActorLabel": label})
                except Exception:
                    pass
            spawned.append({"type": "zone", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "zone", "label": label, "error": str(exc)})

    # 2. PlayerStart actors at participant spawns
    for i, spawn in enumerate(plan.get("participant_spawns", [])):
        pos   = spawn.get("position", {})
        rot   = spawn.get("rotation", {})
        label = f"PlayerStart_{i + 1}_{spawn.get('role', 'player')}"
        try:
            result = await rc_call(
                "/Script/EditorScriptingUtilities.Default__EditorActorSubsystem",
                "SpawnActorFromClass",
                {
                    "ActorClass": "/Script/Engine.PlayerStart",
                    "SpawnTransform": {
                        "Rotation":    {"X": float(rot.get("pitch", 0)),
                                        "Y": float(rot.get("yaw", 0)),
                                        "Z": float(rot.get("roll", 0)), "W": 1},
                        "Translation": {"X": float(pos.get("x", 0)),
                                        "Y": float(pos.get("y", 0)),
                                        "Z": float(pos.get("z", 100))},
                        "Scale3D":     {"X": 1, "Y": 1, "Z": 1},
                    },
                },
            )
            actor_path = result.get("ActorObject", {}).get("ObjectPath", "")
            if actor_path:
                try:
                    await rc_call(actor_path, "SetActorLabel",
                                   {"NewActorLabel": label})
                except Exception:
                    pass
            spawned.append({"type": "player_start", "label": label, "actor_path": actor_path})
        except Exception as exc:
            errors.append({"type": "player_start", "label": label, "error": str(exc)})

    # 3. Save level
    try:
        await rc_call("/Script/UnrealEd.Default__EditorLevelLibrary",
                      "SaveCurrentLevel", generate_transaction=False)
    except Exception as exc:
        errors.append({"type": "save", "error": str(exc)})

    return {
        "status":        "ok" if not errors else "partial",
        "scene_name":    plan.get("name"),
        "actors_spawned": len(spawned),
        "actors":        spawned,
        "errors":        errors,
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
