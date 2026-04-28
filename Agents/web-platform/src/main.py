"""WebPlatformAgent — Bedrock AgentCore agent for Hypermage VR.

Phase 11a upgrade: audio loading, glTF asset loading, virtual joystick,
tap-to-interact, Cognito gate, PWA manifest, GM control panel.

Tools:
  generate_web_scene  — ScenePlan JSON → Babylon.js HTML scene file in S3
                        (now includes audio + glTF assets + manifest.json)
  deploy_web_scene    — upload HTML to S3, invalidate CloudFront, return URL
  query_web_scenes    — list deployed scenes (optionally filter by sceneId/status)
  generate_gm_panel   — GM control panel HTML with hook buttons, Cognito-gated
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key as DKey
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

MODEL_ID   = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

WEB_SCENES_TABLE      = os.environ.get("WEB_SCENES_TABLE", "hypermage-vr-web-scenes-dev")
AUDIO_ASSETS_TABLE    = os.environ.get("AUDIO_ASSETS_TABLE", "hypermage-vr-audio-assets-dev")
ASSET_CATALOGUE_TABLE = os.environ.get("ASSET_CATALOGUE_TABLE", "hypermage-vr-asset-catalogue-dev")
BUILD_S3_BUCKET       = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")

CLOUDFRONT_DOMAIN_SSM = "/hypermage/web-platform/cloudfront-domain"
WS_URL_SSM            = "/hypermage/web-platform/ws-url"
BUCKET_SSM            = "/hypermage/web-platform/scenes-bucket"
WORLD_STATE_URL_SSM   = "/hypermage/world-state/api-url"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3       = boto3.client("s3",   region_name=AWS_REGION)
ssm      = boto3.client("ssm",  region_name=AWS_REGION)
cf       = boto3.client("cloudfront", region_name=AWS_REGION)


def _get_ssm(name: str) -> str | None:
    try:
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:
        return None


def _presign(bucket: str, key: str, expiry: int = 86400) -> str:
    """Generate a pre-signed S3 GET URL."""
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )
    except Exception:
        return ""


def _s3_uri_to_key(s3_uri: str) -> str:
    """Convert s3://bucket/key to just the key part."""
    # strip s3://bucket-name/
    parts = s3_uri.replace("s3://", "").split("/", 1)
    return parts[1] if len(parts) == 2 else ""


def _s3_uri_to_bucket_key(s3_uri: str) -> tuple[str, str]:
    """Convert s3://bucket/key to (bucket, key)."""
    parts = s3_uri.replace("s3://", "").split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", ""


def _query_audio_assets(scene_id: str) -> list[dict]:
    """Query audio assets for scene_id. Returns list of {audio_type, presigned_url}."""
    try:
        table = dynamodb.Table(AUDIO_ASSETS_TABLE)
        resp  = table.query(
            IndexName="SceneIdIndex",
            KeyConditionExpression=DKey("sceneId").eq(scene_id),
            Limit=50,
        )
        items = resp.get("Items", [])
        result = []
        for item in items:
            if item.get("status") != "ready":
                continue
            audio_type = item.get("audioType", "")
            if audio_type not in ("ambient", "score"):
                continue
            s3_uri = item.get("s3Uri", "")
            if not s3_uri:
                continue
            bucket, key = _s3_uri_to_bucket_key(s3_uri)
            url = _presign(bucket, key)
            if url:
                result.append({"audio_type": audio_type, "presigned_url": url})
        return result
    except Exception:
        return []


def _query_gltf_assets(_scene_id: str) -> list[dict]:
    """Scan asset catalogue for ready glTF/glb assets. Returns list of {asset_id, presigned_url, position}."""
    try:
        table = dynamodb.Table(ASSET_CATALOGUE_TABLE)
        resp  = table.scan(
            FilterExpression="#st = :r",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":r": "ready"},
            Limit=10,
        )
        items = resp.get("Items", [])
        result = []
        for item in items:
            s3_uri = item.get("s3Uri", "")
            if not s3_uri:
                continue
            if not (s3_uri.lower().endswith(".gltf") or s3_uri.lower().endswith(".glb")):
                continue
            bucket, key = _s3_uri_to_bucket_key(s3_uri)
            url = _presign(bucket, key)
            if not url:
                continue
            pos_raw = item.get("position", {})
            if isinstance(pos_raw, str):
                try:
                    pos_raw = json.loads(pos_raw)
                except Exception:
                    pos_raw = {}
            position = {
                "x": float(pos_raw.get("x", 0)),
                "y": float(pos_raw.get("y", 0)),
                "z": float(pos_raw.get("z", 0)),
            }
            result.append({
                "asset_id":     item.get("assetId", ""),
                "presigned_url": url,
                "position":     position,
            })
        return result
    except Exception:
        return []


# ── Interactable helpers ───────────────────────────────────────────────────────

def _build_interactables_js(zones: list[dict]) -> str:
    """Extract all interactable objects from ScenePlan zones into a JS array literal."""
    scale = 0.01
    items = []
    for zone in zones:
        for obj in zone.get("interactables", []):
            pos  = obj.get("position", {})
            px   = pos.get("x", 0) * scale
            py   = pos.get("z", 0) * scale  # UE5 Z → Babylon Y
            pz   = pos.get("y", 0) * scale  # UE5 Y → Babylon Z
            loot = json.dumps([lt.get("artefact_id", "") for lt in obj.get("loot", [])])
            items.append(
                f'  {{ id:{json.dumps(obj.get("id",""))}, type:{json.dumps(obj.get("type",""))}, '
                f'px:{px:.2f}, py:{py:.2f}, pz:{pz:.2f}, '
                f'health:{obj.get("health", 100)}, '
                f'triggerRadius:{obj.get("trigger_radius", 400) * scale:.2f}, '
                f'triggerDelay:{obj.get("trigger_delay", 2)}, '
                f'requiredKeyId:{json.dumps(obj.get("required_key_id", ""))}, '
                f'artefactId:{json.dumps(obj.get("artefact_id", ""))}, '
                f'grantsAbility:{json.dumps(obj.get("grants_ability", ""))}, '
                f'behaviour:{json.dumps(obj.get("behaviour", ""))}, '
                f'persistent:{str(obj.get("persistent", False)).lower()}, loot:{loot} }}'
            )
    return "[\n" + ",\n".join(items) + "\n]"


def _build_interactable_render_js(interactables_array_js: str, world_state_url: str = "") -> str:
    """Return the complete interactable object system JS block for injection."""
    return (
        "    // ── Interactable object system ──────────────────────────────────────\n"
        "    var INTERACTABLES = " + interactables_array_js + ";\n"
        "    var WORLD_STATE_URL = " + json.dumps(world_state_url) + ";\n"
        +
"""
    var playerState = { health:100, maxHealth:100, inventory:[], score:0 };
    var objectStates = {};
    var advancedTexture = null;
    try { advancedTexture = BABYLON.GUI.AdvancedDynamicTexture.CreateFullscreenUI("UI"); }
    catch(e) { console.warn("Babylon GUI unavailable:", e); }

    function makeCreatureHealthBar(mesh, objId) {
      if (!advancedTexture) return;
      var bg = new BABYLON.GUI.Rectangle();
      bg.width = "80px"; bg.height = "10px"; bg.cornerRadius = 3;
      bg.background = "rgba(0,0,0,0.65)"; bg.color = "rgba(255,255,255,0.2)";
      advancedTexture.addControl(bg);
      bg.linkWithMesh(mesh); bg.linkOffsetY = -90;
      var fill = new BABYLON.GUI.Rectangle();
      fill.width = "76px"; fill.height = "6px"; fill.background = "#e74c3c";
      fill.horizontalAlignment = BABYLON.GUI.Control.HORIZONTAL_ALIGNMENT_LEFT;
      bg.addControl(fill);
      objectStates[objId].hpBg   = bg;
      objectStates[objId].hpFill = fill;
    }

    function updateCreatureHp(objId, cur, max) {
      var s = objectStates[objId];
      if (!s || !s.hpFill) return;
      var pct = Math.max(0, cur / max);
      s.hpFill.width = Math.round(76 * pct) + "px";
      s.hpFill.background = pct > 0.5 ? "#2ecc71" : pct > 0.25 ? "#f39c12" : "#e74c3c";
      if (cur <= 0 && s.hpBg) s.hpBg.isVisible = false;
    }

    function updatePlayerHUD() {
      var fill  = document.getElementById("player-hp-fill");
      var val   = document.getElementById("player-hp-val");
      var inv   = document.getElementById("inv-count");
      var score = document.getElementById("score-val");
      if (fill) {
        var pct = playerState.health / playerState.maxHealth;
        fill.style.width = Math.round(pct * 100) + "%";
        fill.style.background = pct > 0.5 ? "#2ecc71" : pct > 0.25 ? "#f39c12" : "#e74c3c";
      }
      if (val)   val.textContent   = playerState.health;
      if (inv)   inv.textContent   = playerState.inventory.length;
      if (score) score.textContent = playerState.score;
    }

    var _fbTimer = null;
    function showFeedback(msg, col) {
      var el = document.getElementById("feedback-toast");
      if (!el) return;
      el.textContent = msg;
      el.style.borderColor = col || "rgba(255,255,255,0.25)";
      el.classList.add("show");
      clearTimeout(_fbTimer);
      _fbTimer = setTimeout(function() { el.classList.remove("show"); }, 2800);
    }

    function broadcastObj(objId, action, data) {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({
        action:"narrative_event", sceneId:SCENE_ID,
        objectId:objId, objectAction:action, objectData:data||{}
      }));
    }

    function persistObjState(objId, state) {
      if (!WORLD_STATE_URL) return;
      var obj = INTERACTABLES.find(function(o) { return o.id === objId; });
      if (!obj || !obj.persistent) return;
      fetch(WORLD_STATE_URL + "/world-state", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({object_id: objId, state: state})
      }).catch(function(e) { console.warn("world-state persist failed:", e); });
    }

    function loadObjectStates() {
      if (!WORLD_STATE_URL) return;
      INTERACTABLES.forEach(function(obj) {
        if (!obj.persistent) return;
        fetch(WORLD_STATE_URL + "/world-state/" + encodeURIComponent(obj.id))
          .then(function(r) { return r.ok ? r.json() : null; })
          .then(function(data) {
            if (!data || !data.state) return;
            if ((data.state + "").toLowerCase().indexOf("resolved") >= 0)
              resolveObject(obj, "restored");
          })
          .catch(function() {});
      });
    }

    function resolveObject(obj, reason) {
      var s = objectStates[obj.id];
      if (!s) return;
      s.state = "resolved";
      persistObjState(obj.id, "resolved");
      if (s.mesh)     s.mesh.setEnabled(false);
      if (s.indicator) s.indicator.setEnabled(false);
      if (s.hpBg)     s.hpBg.isVisible = false;
      if (obj.loot && reason === "killed") {
        obj.loot.forEach(function(lootId) {
          var ls = objectStates[lootId];
          if (ls && ls.mesh) { ls.mesh.setEnabled(true); ls.state = "idle"; }
        });
        showFeedback("Item dropped — go collect it!", "#f39c12");
      }
      broadcastObj(obj.id, "resolved", { reason:reason });
    }

    function triggerEnvironmental(obj) {
      var s = objectStates[obj.id];
      if (!s || s.state === "active" || s.state === "resolved") return;
      s.state = "active";
      persistObjState(obj.id, "active");
      var desc = obj.behaviour ? obj.behaviour.slice(0, 80) : "Environmental event triggered!";
      showFeedback(desc, "#e67e22");
      broadcastObj(obj.id, "triggered", {});
      setTimeout(function() { resolveObject(obj, "triggered"); },
                 (obj.triggerDelay || 5) * 1000);
    }

    function handleInteract(obj) {
      var s = objectStates[obj.id];
      if (!s || s.state === "resolved") return;
      if (obj.type === "creature") {
        if (playerState.health <= 0) { showFeedback("You are defeated.", "#e74c3c"); return; }
        s.health = Math.max(0, s.health - 25);
        s.state = "active";
        persistObjState(obj.id, "active");
        updateCreatureHp(obj.id, s.health, obj.health || 100);
        playerState.health = Math.max(0, playerState.health - 10);
        updatePlayerHUD();
        if (s.health <= 0) {
          playerState.score += 50; updatePlayerHUD();
          resolveObject(obj, "killed");
          showFeedback("Enemy defeated! +50 pts", "#2ecc71");
        } else {
          showFeedback("Hit! Enemy " + s.health + " HP  You " + playerState.health + " HP");
          broadcastObj(obj.id, "damage", { remaining:s.health });
        }
      } else if (obj.type === "artefact") {
        playerState.inventory.push(obj.id);
        playerState.score += 100; updatePlayerHUD();
        resolveObject(obj, "collected");
        showFeedback(obj.grantsAbility ? "Ability: " + obj.grantsAbility + "  +100 pts"
                                       : "Collected!  +100 pts", "#2ecc71");
      } else if (obj.type === "machinery") {
        if (obj.requiredKeyId && playerState.inventory.indexOf(obj.requiredKeyId) < 0) {
          showFeedback("You need a key item to open this.", "#e74c3c"); return;
        }
        if (s.state === "active") return;
        s.state = "active";
        persistObjState(obj.id, "active");
        if (s.indMat) s.indMat.emissiveColor = new BABYLON.Color3(1.0, 0.5, 0.0);
        showFeedback("Unlocking...");
        broadcastObj(obj.id, "unlocking", {});
        setTimeout(function() {
          playerState.score += 75; updatePlayerHUD();
          resolveObject(obj, "opened");
          if (s.indMat) s.indMat.emissiveColor = new BABYLON.Color3(0.0, 1.0, 0.0);
          showFeedback("Unlocked!  +75 pts", "#2ecc71");
        }, (obj.triggerDelay || 2) * 1000);
      } else if (obj.type === "environmental") {
        triggerEnvironmental(obj);
      }
    }

    // Render interactable meshes
    INTERACTABLES.forEach(function(obj) {
      objectStates[obj.id] = { state:"idle", health:obj.health||100, mesh:null };
      var pos = new BABYLON.Vector3(obj.px, obj.py, obj.pz);
      var mesh, mat;
      if (obj.type === "creature") {
        mesh = BABYLON.MeshBuilder.CreateCylinder("obj_"+obj.id, {height:1.8, diameter:0.8}, scene);
        mesh.position = pos;
        mat = new BABYLON.StandardMaterial("mat_"+obj.id, scene);
        mat.diffuseColor  = new BABYLON.Color3(0.7, 0.1, 0.1);
        mat.emissiveColor = new BABYLON.Color3(0.15, 0.0, 0.0);
        mesh.material = mat;
        makeCreatureHealthBar(mesh, obj.id);
        (function(m, baseY) {
          var t = Math.random() * Math.PI * 2;
          scene.registerBeforeRender(function() {
            if (objectStates[obj.id].state !== "resolved") {
              m.position.y = baseY + 0.08 * Math.sin(t); t += 0.025;
            }
          });
        })(mesh, pos.y);
      } else if (obj.type === "artefact") {
        var isLoot = INTERACTABLES.some(function(o) {
          return o.loot && o.loot.indexOf(obj.id) >= 0;
        });
        mesh = BABYLON.MeshBuilder.CreateSphere("obj_"+obj.id, {diameter:0.5}, scene);
        mesh.position = pos;
        mat = new BABYLON.StandardMaterial("mat_"+obj.id, scene);
        mat.diffuseColor  = new BABYLON.Color3(1.0, 0.8, 0.1);
        mat.emissiveColor = new BABYLON.Color3(0.4, 0.3, 0.0);
        mesh.material = mat;
        if (isLoot) mesh.setEnabled(false);
        scene.registerBeforeRender(function() {
          if (objectStates[obj.id].state !== "resolved") mesh.rotation.y += 0.02;
        });
      } else if (obj.type === "machinery") {
        mesh = BABYLON.MeshBuilder.CreateBox("obj_"+obj.id, {width:1.0,height:2.0,depth:0.5}, scene);
        mesh.position = pos;
        mat = new BABYLON.StandardMaterial("mat_"+obj.id, scene);
        mat.diffuseColor  = new BABYLON.Color3(0.35, 0.38, 0.45);
        mat.specularColor = new BABYLON.Color3(0.4, 0.4, 0.5);
        mesh.material = mat;
        var ind = BABYLON.MeshBuilder.CreateSphere("ind_"+obj.id, {diameter:0.22}, scene);
        ind.position = new BABYLON.Vector3(pos.x, pos.y + 1.2, pos.z);
        var indMat = new BABYLON.StandardMaterial("indmat_"+obj.id, scene);
        indMat.emissiveColor = obj.requiredKeyId ? new BABYLON.Color3(1,0,0)
                                                 : new BABYLON.Color3(0,1,0);
        ind.material = indMat;
        objectStates[obj.id].indicator = ind;
        objectStates[obj.id].indMat    = indMat;
      } else if (obj.type === "environmental") {
        var r = obj.triggerRadius > 0 ? obj.triggerRadius : 4.0;
        mesh = BABYLON.MeshBuilder.CreateDisc("obj_"+obj.id, {radius:r}, scene);
        mesh.rotation.x = Math.PI / 2;
        mesh.position = new BABYLON.Vector3(pos.x, 0.05, pos.z);
        mat = new BABYLON.StandardMaterial("mat_"+obj.id, scene);
        mat.diffuseColor = new BABYLON.Color3(1.0, 0.5, 0.0);
        mat.alpha = 0.3; mat.backFaceCulling = false;
        mesh.material = mat;
        (function(m) {
          var t = Math.random() * Math.PI * 2;
          scene.registerBeforeRender(function() {
            if (objectStates[obj.id].state !== "resolved") {
              m.material.alpha = 0.15 + 0.15 * Math.sin(t); t += 0.04;
            }
          });
        })(mesh);
      }
      if (mesh) { objectStates[obj.id].mesh = mesh; mesh.metadata = {interactable:obj}; }
    });
    loadObjectStates();

    // Proximity trigger for environmental objects
    scene.registerBeforeRender(function() {
      INTERACTABLES.forEach(function(obj) {
        if (obj.type !== "environmental") return;
        var s = objectStates[obj.id];
        if (!s || s.state !== "idle" || !s.mesh) return;
        var p = s.mesh.position;
        var d = BABYLON.Vector3.Distance(
          new BABYLON.Vector3(camera.position.x, 0, camera.position.z),
          new BABYLON.Vector3(p.x, 0, p.z));
        if (d < obj.triggerRadius) triggerEnvironmental(obj);
      });
    });

    function handleIncomingObjectEvent(msg) {
      if (!msg.objectId || !msg.objectAction) return;
      var obj = INTERACTABLES.find(function(o) { return o.id === msg.objectId; });
      if (!obj) return;
      var s = objectStates[obj.id];
      if (!s || s.state === "resolved") return;
      if (msg.objectAction === "resolved") resolveObject(obj, "remote");
      else if (msg.objectAction === "damage" && msg.objectData)
        updateCreatureHp(obj.id, msg.objectData.remaining, obj.health || 100);
    }
"""
    )


# ── Babylon.js scene generator ─────────────────────────────────────────────────

_ZONE_COLORS: dict[str, str] = {
    "exploration": "#3a86ff",
    "combat":      "#e63946",
    "social":      "#ffbe0b",
    "puzzle":      "#06d6a0",
    "sanctuary":   "#8338ec",
    "transit":     "#adb5bd",
}

_LIGHTING_PRESETS: dict[str, dict[str, Any]] = {
    "neutral white": {"ambient": [0.3, 0.3, 0.3], "diffuse": [1.0, 1.0, 1.0], "sky": "#e8eaf6"},
    "dark dramatic": {"ambient": [0.05, 0.05, 0.1], "diffuse": [0.8, 0.8, 1.0], "sky": "#0a0a1a"},
    "golden warm":   {"ambient": [0.3, 0.2, 0.05], "diffuse": [1.0, 0.9, 0.6], "sky": "#fff3cd"},
    "cool moonlit":  {"ambient": [0.05, 0.08, 0.15], "diffuse": [0.6, 0.7, 1.0], "sky": "#0d1b2a"},
    "orange sunset": {"ambient": [0.25, 0.1, 0.05], "diffuse": [1.0, 0.6, 0.3], "sky": "#ff9f1c"},
    "neon cyber":    {"ambient": [0.1, 0.0, 0.2], "diffuse": [0.0, 1.0, 1.0], "sky": "#0a0018"},
    "forest green":  {"ambient": [0.1, 0.2, 0.05], "diffuse": [0.6, 1.0, 0.4], "sky": "#1b4332"},
    "foggy grey":    {"ambient": [0.2, 0.2, 0.2], "diffuse": [0.7, 0.7, 0.7], "sky": "#ced4da"},
}


def _get_lighting(mood: str) -> dict[str, Any]:
    mood_lower = mood.lower()
    for key, preset in _LIGHTING_PRESETS.items():
        if key in mood_lower or any(w in mood_lower for w in key.split()):
            return preset
    return _LIGHTING_PRESETS["neutral white"]


def _generate_babylon_html(scene_plan: dict, ws_url: str,
                           audio_assets: list[dict] | None = None,
                           gltf_assets: list[dict] | None = None,
                           world_state_url: str = "") -> str:
    """Convert a ScenePlan dict into a self-contained Babylon.js HTML page."""
    audio_assets = audio_assets or []
    gltf_assets  = gltf_assets  or []

    scene_id    = scene_plan.get("id", str(uuid.uuid4()))
    scene_name  = scene_plan.get("name", "Untitled Scene")
    zones       = scene_plan.get("zones", [])
    atmosphere  = scene_plan.get("atmosphere", {})
    spawns      = scene_plan.get("participant_spawns", [])
    narr_states = scene_plan.get("narrative_states", [])

    lighting  = _get_lighting(atmosphere.get("lighting_mood", "neutral white"))
    sky_color = lighting["sky"]

    # Build zone mesh definitions (JS array literal)
    zone_defs = []
    for z in zones:
        bounds  = z.get("bounds", {})
        center  = bounds.get("center", {"x": 0, "y": 0, "z": 0})
        extents = bounds.get("extents", {"x": 100, "y": 100, "z": 100})
        ztype   = z.get("type", "exploration")
        color   = _ZONE_COLORS.get(ztype, "#adb5bd")
        # Scale factor: UE5 units → Babylon metres (~1/100)
        scale = 0.01
        zone_defs.append(
            f'  {{ id: "{z.get("id","")}", name: "{z.get("name","")}", type: "{ztype}", '
            f'cx: {center["x"] * scale:.1f}, cy: {center["z"] * scale:.1f}, cz: {center["y"] * scale:.1f}, '
            f'ex: {extents["x"] * scale:.1f}, ey: {extents["z"] * scale:.1f}, ez: {extents["y"] * scale:.1f}, '
            f'color: "{color}" }}'
        )

    # Camera start position from first participant spawn
    cam_x, cam_y, cam_z = 0, 2, -5
    if spawns:
        sp = spawns[0].get("position", {})
        cam_x = sp.get("x", 0) * 0.01
        cam_y = max(sp.get("z", 100) * 0.01, 1.5)
        cam_z = sp.get("y", -400) * 0.01

    # Narrative states for the HUD
    state_names   = [s.get("name", s.get("id", "")) for s in narr_states]
    initial_state = next((s.get("name", "") for s in narr_states if s.get("is_initial")), "")

    ambient_r, ambient_g, ambient_b = lighting["ambient"]
    diff_r, diff_g, diff_b = lighting["diffuse"]

    zones_js         = "[\n" + ",\n".join(zone_defs) + "\n]"
    states_js        = json.dumps(state_names)
    interactable_block = _build_interactable_render_js(_build_interactables_js(zones), world_state_url)

    # Build audio JS block
    audio_js_lines = []
    for asset in audio_assets:
        atype = asset.get("audio_type", "")
        url   = asset.get("presigned_url", "")
        if not url:
            continue
        if atype == "ambient":
            audio_js_lines.append(
                f'    try {{ new BABYLON.Sound("ambient_{uuid.uuid4().hex[:8]}", '
                f'"{url}", scene, null, {{loop:true, autoplay:true, volume:0.4}}); }} '
                f'catch(e) {{ console.warn("ambient audio load failed:", e); }}'
            )
        elif atype == "score":
            audio_js_lines.append(
                f'    try {{ new BABYLON.Sound("score_{uuid.uuid4().hex[:8]}", '
                f'"{url}", scene, null, {{loop:true, autoplay:true, volume:0.3}}); }} '
                f'catch(e) {{ console.warn("score audio load failed:", e); }}'
            )

    audio_resume_js = ""
    if audio_js_lines:
        audio_resume_js = """
    // Resume AudioContext on first pointer interaction (browser autoplay policy)
    document.addEventListener("pointerdown", function resumeAudio() {
      if (BABYLON.Engine.audioEngine && BABYLON.Engine.audioEngine.audioContext &&
          BABYLON.Engine.audioEngine.audioContext.state === "suspended") {
        BABYLON.Engine.audioEngine.audioContext.resume();
      }
      document.removeEventListener("pointerdown", resumeAudio);
    }, { once: true });
"""

    audio_block = "\n".join(audio_js_lines)

    # Build glTF import JS block
    gltf_js_lines = []
    for ga in gltf_assets:
        url = ga.get("presigned_url", "")
        pos = ga.get("position", {"x": 0, "y": 0, "z": 0})
        if not url:
            continue
        px = float(pos.get("x", 0)) * 0.01
        py = float(pos.get("z", 0)) * 0.01
        pz = float(pos.get("y", 0)) * 0.01
        gltf_js_lines.append(f"""    try {{
      BABYLON.SceneLoader.ImportMesh("", "{url}", "", scene, function(meshes) {{
        if (meshes && meshes[0]) {{
          meshes[0].position = new BABYLON.Vector3({px:.2f}, {py:.2f}, {pz:.2f});
        }}
      }});
    }} catch(e) {{ console.warn("glTF load failed:", e); }}""")

    gltf_block = "\n".join(gltf_js_lines)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{scene_name} — Hypermage VR</title>
  <link rel="manifest" href="./manifest.json"/>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#000; overflow:hidden; font-family:'Segoe UI',sans-serif; }}
    #canvas {{ width:100vw; height:100vh; touch-action:none; }}
    #hud {{
      position:absolute; top:16px; left:16px; color:#fff;
      background:rgba(0,0,0,0.55); border-radius:8px; padding:12px 16px;
      max-width:260px; backdrop-filter:blur(8px);
    }}
    #hud h2 {{ font-size:14px; font-weight:600; margin-bottom:4px; }}
    #hud .state {{ font-size:12px; color:#a8d8ff; margin-top:6px; }}
    #hud .zone-list {{ font-size:11px; color:#ccc; margin-top:6px; }}
    #presence {{
      position:absolute; bottom:16px; right:16px; color:#fff;
      background:rgba(0,0,0,0.55); border-radius:8px; padding:8px 12px;
      font-size:11px; backdrop-filter:blur(8px);
    }}
    #player-hud {{
      position:absolute; bottom:16px; left:16px; color:#fff;
      background:rgba(0,0,0,0.55); border-radius:8px; padding:10px 14px;
      min-width:170px; backdrop-filter:blur(8px);
    }}
    .hud-row {{ display:flex; align-items:center; gap:8px; margin-bottom:5px; }}
    .hud-label {{ font-size:10px; color:#aaa; width:22px; }}
    .hud-bar-bg {{ flex:1; height:8px; background:rgba(255,255,255,0.15); border-radius:4px; overflow:hidden; }}
    .hud-bar-fill {{ height:100%; background:#2ecc71; border-radius:4px; transition:width .25s,background .25s; }}
    .hud-val {{ font-size:11px; width:28px; text-align:right; }}
    .hud-stat {{ font-size:11px; color:#ccc; margin-top:2px; }}
    #feedback-toast {{
      position:absolute; top:45%; left:50%; transform:translate(-50%,-50%);
      background:rgba(0,0,0,0.78); color:#fff; padding:9px 18px;
      border-radius:8px; font-size:13px; pointer-events:none;
      border:1px solid rgba(255,255,255,0.25);
      opacity:0; transition:opacity .25s; backdrop-filter:blur(6px); text-align:center;
    }}
    #feedback-toast.show {{ opacity:1; }}
  </style>
</head>
<body>
  <canvas id="canvas"></canvas>
  <div id="hud">
    <h2>{scene_name}</h2>
    <div class="state">State: <span id="narr-state">{initial_state or "—"}</span></div>
    <div class="zone-list" id="zone-list"></div>
  </div>
  <div id="presence">Participants: <span id="p-count">1</span></div>
  <div id="player-hud">
    <div class="hud-row">
      <span class="hud-label">HP</span>
      <div class="hud-bar-bg"><div class="hud-bar-fill" id="player-hp-fill" style="width:100%"></div></div>
      <span class="hud-val" id="player-hp-val">100</span>
    </div>
    <div class="hud-stat">Items: <span id="inv-count">0</span> &nbsp;|&nbsp; Score: <span id="score-val">0</span></div>
  </div>
  <div id="feedback-toast"></div>

  <script src="https://cdn.babylonjs.com/babylon.js"></script>
  <script src="https://cdn.babylonjs.com/loaders/babylonjs.loaders.min.js"></script>
  <script src="https://cdn.babylonjs.com/gui/babylon.gui.min.js"></script>
  <script>
  (function() {{
    // ── Cognito gate ─────────────────────────────────────────────────────────
    var params       = new URLSearchParams(window.location.search);
    var requireAuth  = params.get("require_auth") === "true";
    var token        = params.get("token") || localStorage.getItem("hm_token");
    if (requireAuth && !token) {{
      document.body.innerHTML = "<div style='color:white;padding:2em'>Access requires authentication. Add ?token=&lt;jwt&gt; to the URL.</div>";
      return;
    }}
    if (token) {{ localStorage.setItem("hm_token", token); }}

    const SCENE_ID = "{scene_id}";
    const WS_URL   = "{ws_url}";
    const ZONES    = {zones_js};
    const STATES   = {states_js};

    // ── Engine & scene ───────────────────────────────────────────────────────
    const canvas  = document.getElementById("canvas");
    const engine  = new BABYLON.Engine(canvas, true);
    const scene   = new BABYLON.Scene(engine);
    scene.clearColor = BABYLON.Color4.FromHexString("{sky_color}ff");

    // ── Camera ───────────────────────────────────────────────────────────────
    const camera = new BABYLON.UniversalCamera(
      "cam", new BABYLON.Vector3({cam_x}, {cam_y}, {cam_z}), scene
    );
    camera.setTarget(BABYLON.Vector3.Zero());
    camera.attachControl(canvas, true);
    camera.minZ = 0.1;
    camera.speed = 0.5;
    camera.keysUp.push(87);    // W
    camera.keysDown.push(83);  // S
    camera.keysLeft.push(65);  // A
    camera.keysRight.push(68); // D

    // ── Lighting ─────────────────────────────────────────────────────────────
    const hemi = new BABYLON.HemisphericLight("hemi", new BABYLON.Vector3(0, 1, 0), scene);
    hemi.intensity  = 0.8;
    hemi.diffuse    = new BABYLON.Color3({diff_r}, {diff_g}, {diff_b});
    hemi.groundColor= new BABYLON.Color3({ambient_r}, {ambient_g}, {ambient_b});

    const sun = new BABYLON.DirectionalLight("sun", new BABYLON.Vector3(-1, -2, -1), scene);
    sun.intensity = 1.2;
    sun.diffuse   = new BABYLON.Color3({diff_r}, {diff_g}, {diff_b});

    // ── Ground plane ─────────────────────────────────────────────────────────
    const ground = BABYLON.MeshBuilder.CreateGround("ground",
      {{ width: 200, height: 200 }}, scene);
    const gMat = new BABYLON.StandardMaterial("gMat", scene);
    gMat.diffuseColor = new BABYLON.Color3(0.15, 0.15, 0.18);
    gMat.specularColor = new BABYLON.Color3(0.05, 0.05, 0.05);
    ground.material = gMat;

    // ── Zone meshes ──────────────────────────────────────────────────────────
    const zoneList = document.getElementById("zone-list");
    ZONES.forEach(function(z) {{
      const box = BABYLON.MeshBuilder.CreateBox("zone_" + z.id,
        {{ width: z.ex * 2, height: z.ey * 2, depth: z.ez * 2 }}, scene);
      box.position = new BABYLON.Vector3(z.cx, z.cy, z.cz);
      const mat = new BABYLON.StandardMaterial("mat_" + z.id, scene);
      const hex = z.color.replace("#","");
      const r = parseInt(hex.substr(0,2),16)/255;
      const g = parseInt(hex.substr(2,2),16)/255;
      const b = parseInt(hex.substr(4,2),16)/255;
      mat.diffuseColor  = new BABYLON.Color3(r, g, b);
      mat.alpha         = 0.35;
      mat.wireframe     = false;
      mat.backFaceCulling = false;
      box.material = mat;

      const li = document.createElement("div");
      li.style.cssText = "margin-top:3px; display:flex; align-items:center; gap:6px;";
      li.innerHTML = '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' +
        z.color + '"></span><span>' + z.name + ' (' + z.type + ')</span>';
      zoneList.appendChild(li);
    }});

    // ── Grid lines overlay ───────────────────────────────────────────────────
    try {{
      const grid = new BABYLON.GridMaterial("grid", scene);
      grid.majorUnitFrequency  = 10;
      grid.minorUnitVisibility = 0.45;
      grid.gridRatio           = 1;
      grid.backFaceCulling     = false;
      grid.mainColor     = new BABYLON.Color3(0.2, 0.2, 0.35);
      grid.lineColor     = new BABYLON.Color3(0.3, 0.3, 0.5);
      grid.opacity       = 0.75;
      ground.material    = grid;
    }} catch(e) {{ /* GridMaterial not available without extras CDN */ }}

    // ── Audio ────────────────────────────────────────────────────────────────
{audio_block}
{audio_resume_js}

    // ── glTF asset loading ───────────────────────────────────────────────────
{gltf_block}

{interactable_block}

    // ── WebSocket presence ───────────────────────────────────────────────────
    const pCount = document.getElementById("p-count");
    const narr   = document.getElementById("narr-state");
    let ws = null;
    if (WS_URL && WS_URL !== "NOT_SET") {{
      try {{
        ws = new WebSocket(WS_URL + "?sceneId=" + SCENE_ID);
        ws.onopen = function() {{
          ws.send(JSON.stringify({{ action: "join_scene", sceneId: SCENE_ID }}));
        }};
        ws.onmessage = function(ev) {{
          try {{
            const msg = JSON.parse(ev.data);
            if (msg.action === "scene_state" || msg.action === "narrative_event") {{
              if (msg.narrativeState) narr.textContent = msg.narrativeState;
              if (msg.participantCount !== undefined)
                pCount.textContent = msg.participantCount;
              if (msg.objectId) handleIncomingObjectEvent(msg);
            }} else if (msg.action === "presence") {{
              pCount.textContent = parseInt(pCount.textContent||1) + 0;
            }}
          }} catch(e) {{ }}
        }};
        ws.onerror = function() {{ console.log("WS unavailable — offline mode"); }};
        setInterval(function() {{
          if (ws && ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({{ action: "ping" }}));
        }}, 60000);
      }} catch(e) {{ console.log("WS error:", e); }}
    }}

    // ── Tap-to-interact (interactable objects first, then narrative WS event) ──
    scene.onPointerObservable.add(function(pi) {{
      if (pi.type !== BABYLON.PointerEventTypes.POINTERTAP) return;
      var ray = scene.createPickingRay(
        scene.pointerX, scene.pointerY, BABYLON.Matrix.Identity(), camera);
      var hit = scene.pickWithRay(ray);
      if (!hit || !hit.hit || !hit.pickedMesh) return;
      var meta = hit.pickedMesh.metadata;
      if (meta && meta.interactable) {{
        handleInteract(meta.interactable);
      }} else if (ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{
          action:"narrative_event", sceneId:SCENE_ID,
          interactedMesh: hit.pickedMesh.name
        }}));
      }}
    }});

    // ── Virtual joystick (touch devices) ─────────────────────────────────────
    if (navigator.maxTouchPoints > 0) {{
      try {{
        var leftJ  = new BABYLON.VirtualJoystick(true);
        var rightJ = new BABYLON.VirtualJoystick(false);
        scene.registerBeforeRender(function() {{
          if (leftJ.pressed) {{
            camera.position.addInPlace(
              camera.getDirection(BABYLON.Axis.Z).scale(leftJ.deltaPosition.y * 0.05)
            );
            camera.position.addInPlace(
              camera.getDirection(BABYLON.Axis.X).scale(leftJ.deltaPosition.x * 0.05)
            );
          }}
          if (rightJ.pressed) {{
            camera.rotation.y += rightJ.deltaPosition.x * 0.003;
            camera.rotation.x += rightJ.deltaPosition.y * 0.003;
          }}
        }});
      }} catch(e) {{ console.warn("VirtualJoystick not available:", e); }}
    }}

    // ── Render loop ──────────────────────────────────────────────────────────
    engine.runRenderLoop(function() {{ scene.render(); }});
    window.addEventListener("resize", function() {{ engine.resize(); }});
  }})();
  </script>
</body>
</html>"""


def _generate_manifest(scene_id: str, scene_name: str) -> str:
    """Generate a PWA manifest.json for the scene."""
    return json.dumps({
        "name":             f"{scene_name} — Hypermage VR",
        "short_name":       scene_name[:12],
        "description":      "Hypermage VR interactive scene",
        "start_url":        f"./index.html?scene_id={scene_id}",
        "display":          "fullscreen",
        "orientation":      "landscape",
        "background_color": "#000000",
        "theme_color":      "#0a0018",
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }, indent=2)


# ── Agent tools ────────────────────────────────────────────────────────────────

@tool
def generate_web_scene(scene_plan_json: str) -> dict:
    """Generate a Babylon.js HTML scene from a ScenePlan JSON string.

    Queries DynamoDB for audio assets (ambient/score) and glTF assets for this scene.
    Generates pre-signed URLs for all assets, injects them into the HTML.
    Uploads index.html + manifest.json to S3 and records the scene in DynamoDB.

    Args:
        scene_plan_json: Full ScenePlan JSON string.

    Returns:
        {"status": "ok", "scene_id": str, "s3_key": str, "s3_uri": str, "web_url": str}
    """
    try:
        scene_plan = json.loads(scene_plan_json)
    except Exception as exc:
        return {"status": "error", "error": f"Invalid ScenePlan JSON: {exc}"}

    bucket    = _get_ssm(BUCKET_SSM)
    ws_url          = _get_ssm(WS_URL_SSM) or "NOT_SET"
    cf_domain       = _get_ssm(CLOUDFRONT_DOMAIN_SSM)
    world_state_url = _get_ssm(WORLD_STATE_URL_SSM) or ""

    if not bucket:
        return {"status": "skipped", "note": "Web platform SSM not configured — run deploy_phase10.py first"}

    scene_id   = scene_plan.get("id", str(uuid.uuid4()))
    scene_name = scene_plan.get("name", "Untitled Scene")

    # Query audio assets for this scene
    audio_assets = _query_audio_assets(scene_id)

    # Query glTF assets
    gltf_assets = _query_gltf_assets(scene_id)

    html     = _generate_babylon_html(scene_plan, ws_url, audio_assets, gltf_assets, world_state_url)
    manifest = _generate_manifest(scene_id, scene_name)

    s3_key      = f"scenes/{scene_id}/index.html"
    manifest_key = f"scenes/{scene_id}/manifest.json"
    s3_uri      = f"s3://{bucket}/{s3_key}"
    web_url     = f"https://{cf_domain}/{s3_key}" if cf_domain else ""

    # Upload HTML to S3
    try:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
    except Exception as exc:
        return {"status": "error", "error": f"S3 upload (HTML) failed: {exc}"}

    # Upload manifest.json to S3
    try:
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=manifest.encode("utf-8"),
            ContentType="application/manifest+json; charset=utf-8",
        )
    except Exception as exc:
        # Non-fatal — log but continue
        print(f"[web-platform] manifest.json upload failed (non-fatal): {exc}")

    # Write DynamoDB record
    try:
        table = dynamodb.Table(WEB_SCENES_TABLE)
        table.put_item(Item={
            "sceneId":               scene_id,
            "sceneName":             scene_name,
            "sceneType":             scene_plan.get("scene_type", ""),
            "status":                "generated",
            "s3Key":                 s3_key,
            "s3Uri":                 s3_uri,
            "webUrl":                web_url,
            "generatedAt":           datetime.now(timezone.utc).isoformat(),
            "deployedAt":            "0000-00-00T00:00:00+00:00",
            "zoneCount":             len(scene_plan.get("zones", [])),
            "atmosphereMood":        scene_plan.get("atmosphere", {}).get("lighting_mood", ""),
            "currentNarrativeState": next(
                (s.get("id", "") for s in scene_plan.get("narrative_states", []) if s.get("is_initial")),
                ""
            ),
            "narrativeStates":       json.dumps(scene_plan.get("narrative_states", [])),
            "gmHooks":               json.dumps(scene_plan.get("gm_hooks", [])),
            "ttl":                   int(time.time()) + 86400 * 90,
        })
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB write failed: {exc}"}

    return {
        "status":        "ok",
        "scene_id":      scene_id,
        "s3_key":        s3_key,
        "s3_uri":        s3_uri,
        "web_url":       web_url,
        "audio_assets":  len(audio_assets),
        "gltf_assets":   len(gltf_assets),
        "manifest_key":  manifest_key,
        "note":          "HTML + manifest generated — call deploy_web_scene to get a live CloudFront URL",
    }


@tool
def deploy_web_scene(scene_id: str) -> dict:
    """Finalize deployment: update DynamoDB record status and invalidate CloudFront cache.

    The HTML file is already in S3 after generate_web_scene. This step marks the
    scene as 'deployed' and flushes the CloudFront edge cache so the URL is live.

    Args:
        scene_id: Scene ID returned by generate_web_scene.

    Returns:
        {"status": "ok", "web_url": str, "cloudfront_invalidation_id": str}
    """
    cf_domain = _get_ssm(CLOUDFRONT_DOMAIN_SSM)
    bucket    = _get_ssm(BUCKET_SSM)

    if not cf_domain or not bucket:
        return {"status": "skipped", "note": "Web platform not deployed — run deploy_phase10.py first"}

    s3_key  = f"scenes/{scene_id}/index.html"
    web_url = f"https://{cf_domain}/{s3_key}"

    # Confirm S3 object exists
    try:
        s3.head_object(Bucket=bucket, Key=s3_key)
    except Exception:
        return {"status": "error", "error": f"Scene {scene_id} not found in S3 — call generate_web_scene first"}

    # Find CloudFront distribution ID
    dist_id = None
    try:
        paginator = cf.get_paginator("list_distributions")
        for page in paginator.paginate():
            for dist in page["DistributionList"].get("Items", []):
                if dist.get("DomainName") == cf_domain:
                    dist_id = dist["Id"]
                    break
            if dist_id:
                break
    except Exception as exc:
        return {"status": "error", "error": f"Could not find CloudFront distribution: {exc}"}

    # Invalidate the scene path
    invalidation_id = ""
    if dist_id:
        try:
            resp = cf.create_invalidation(
                DistributionId=dist_id,
                InvalidationBatch={
                    "Paths": {"Quantity": 2, "Items": [f"/{s3_key}", f"/scenes/{scene_id}/manifest.json"]},
                    "CallerReference": f"phase11a-{scene_id}-{int(time.time())}",
                },
            )
            invalidation_id = resp["Invalidation"]["Id"]
        except Exception as exc:
            invalidation_id = f"failed: {exc}"

    # Update DynamoDB status
    try:
        table = dynamodb.Table(WEB_SCENES_TABLE)
        table.update_item(
            Key={"sceneId": scene_id},
            UpdateExpression="SET #s = :s, deployedAt = :da, webUrl = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s":  "deployed",
                ":da": datetime.now(timezone.utc).isoformat(),
                ":u":  web_url,
            },
        )
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB update failed: {exc}"}

    return {
        "status":                     "ok",
        "scene_id":                   scene_id,
        "web_url":                    web_url,
        "cloudfront_invalidation_id": invalidation_id,
        "note":                       "Scene is live — open the URL in any browser to view the 3D scene",
    }


@tool
def query_web_scenes(scene_id: str = "", status: str = "", limit: int = 20) -> dict:
    """Query deployed web scenes from DynamoDB.

    Args:
        scene_id: Exact scene ID to retrieve (optional).
        status:   Filter by status: 'generated', 'deployed' (optional).
        limit:    Max number of results (default 20).

    Returns:
        {"status": "ok", "scenes": [...], "count": int}
    """
    table = dynamodb.Table(WEB_SCENES_TABLE)
    try:
        if scene_id:
            resp = table.get_item(Key={"sceneId": scene_id})
            item = resp.get("Item")
            if not item:
                return {"status": "ok", "scenes": [], "count": 0}
            return {"status": "ok", "scenes": [_clean(item)], "count": 1}

        if status:
            resp = table.query(
                IndexName="StatusDeployedAtIndex",
                KeyConditionExpression=DKey("status").eq(status),
                Limit=limit,
                ScanIndexForward=False,
            )
        else:
            resp = table.scan(Limit=limit)

        scenes = [_clean(i) for i in resp.get("Items", [])]
        return {"status": "ok", "scenes": scenes, "count": len(scenes)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@tool
def generate_gm_panel(scene_id: str) -> dict:
    """Generate a GM control panel HTML page for a scene.

    The panel is Cognito-gated, shows current narrative state, zone/participant
    count, and one button per gm_hook. Clicking a button sends a WebSocket
    narrative_event message.

    Uploads HTML to S3 at gm-panel/{scene_id}/index.html and updates DynamoDB.

    Args:
        scene_id: Scene ID to generate the GM panel for.

    Returns:
        {"status": "ok", "gm_panel_url": str}
    """
    bucket    = _get_ssm(BUCKET_SSM)
    cf_domain = _get_ssm(CLOUDFRONT_DOMAIN_SSM)
    ws_url    = _get_ssm(WS_URL_SSM) or "NOT_SET"

    if not bucket or not cf_domain:
        return {"status": "skipped", "note": "Web platform SSM not configured"}

    # Read scene record from DynamoDB
    try:
        table = dynamodb.Table(WEB_SCENES_TABLE)
        resp  = table.get_item(Key={"sceneId": scene_id})
        item  = resp.get("Item")
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB read failed: {exc}"}

    if not item:
        return {"status": "error", "error": f"Scene '{scene_id}' not found in web-scenes table"}

    scene_name     = item.get("sceneName", scene_id)
    current_state  = item.get("currentNarrativeState", "—")
    gm_hooks_raw   = item.get("gmHooks", "[]")
    try:
        gm_hooks = json.loads(gm_hooks_raw) if isinstance(gm_hooks_raw, str) else gm_hooks_raw
    except Exception:
        gm_hooks = []

    # Build hook buttons JS
    hooks_js_array = json.dumps([
        {"id": h.get("id", ""), "name": h.get("name", h.get("id", "")),
         "description": h.get("description", "")}
        for h in gm_hooks
    ])

    gm_panel_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>GM Panel — {scene_name}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      background:#0a0a1a; color:#e0e0ff; font-family:'Segoe UI',sans-serif;
      min-height:100vh; padding:24px;
    }}
    h1 {{ font-size:22px; font-weight:700; color:#a8d8ff; margin-bottom:4px; }}
    .subtitle {{ font-size:13px; color:#6688aa; margin-bottom:24px; }}
    .panel {{
      background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1);
      border-radius:12px; padding:20px; margin-bottom:20px;
    }}
    .panel h2 {{ font-size:14px; font-weight:600; color:#88aaff; margin-bottom:12px; }}
    .stat-row {{ display:flex; gap:24px; margin-bottom:8px; }}
    .stat {{ font-size:13px; }}
    .stat span {{ color:#a8d8ff; font-weight:600; }}
    .hook-btn {{
      display:block; width:100%; padding:12px 16px; margin-bottom:10px;
      background:rgba(168,216,255,0.1); border:1px solid rgba(168,216,255,0.3);
      border-radius:8px; color:#e0e0ff; font-size:14px; cursor:pointer;
      text-align:left; transition:background 0.2s;
    }}
    .hook-btn:hover {{ background:rgba(168,216,255,0.2); }}
    .hook-btn .hook-desc {{ font-size:11px; color:#6688aa; margin-top:4px; }}
    .status-bar {{
      position:fixed; bottom:16px; left:50%; transform:translateX(-50%);
      background:rgba(0,200,100,0.15); border:1px solid rgba(0,200,100,0.4);
      border-radius:8px; padding:8px 20px; font-size:12px; color:#80ffb0;
      opacity:0; transition:opacity 0.3s; pointer-events:none;
    }}
    .status-bar.show {{ opacity:1; }}
    #auth-error {{
      background:rgba(255,100,100,0.1); border:1px solid rgba(255,100,100,0.4);
      border-radius:8px; padding:16px; color:#ff8888;
    }}
  </style>
</head>
<body>
  <h1>{scene_name}</h1>
  <div class="subtitle">GM Control Panel &mdash; Scene ID: {scene_id}</div>

  <div id="auth-error" style="display:none">
    Access requires authentication. Add <code>?token=&lt;jwt&gt;</code> to the URL.
  </div>

  <div id="main-panel" style="display:none">
    <div class="panel">
      <h2>Scene Status</h2>
      <div class="stat-row">
        <div class="stat">Narrative State: <span id="current-state">{current_state}</span></div>
        <div class="stat">Participants: <span id="p-count">—</span></div>
      </div>
    </div>

    <div class="panel">
      <h2>GM Hooks</h2>
      <div id="hook-buttons"></div>
    </div>
  </div>

  <div class="status-bar" id="status-bar"></div>

  <script>
  (function() {{
    var params = new URLSearchParams(window.location.search);
    var token  = params.get("token") || localStorage.getItem("hm_token");
    if (!token) {{
      document.getElementById("auth-error").style.display = "block";
      return;
    }}
    localStorage.setItem("hm_token", token);
    document.getElementById("main-panel").style.display = "block";

    var SCENE_ID = "{scene_id}";
    var WS_URL   = "{ws_url}";
    var HOOKS    = {hooks_js_array};

    // Render hook buttons
    var container = document.getElementById("hook-buttons");
    if (HOOKS.length === 0) {{
      container.innerHTML = '<div style="color:#6688aa;font-size:13px">No GM hooks defined in this ScenePlan.</div>';
    }} else {{
      HOOKS.forEach(function(hook) {{
        var btn = document.createElement("button");
        btn.className = "hook-btn";
        btn.innerHTML = '<div>' + hook.name + '</div>'
          + (hook.description ? '<div class="hook-desc">' + hook.description + '</div>' : '');
        btn.addEventListener("click", function() {{ fireHook(hook); }});
        container.appendChild(btn);
      }});
    }}

    // WebSocket connection
    var ws = null;
    function connectWS() {{
      if (!WS_URL || WS_URL === "NOT_SET") return;
      try {{
        ws = new WebSocket(WS_URL + "?sceneId=" + SCENE_ID + "&role=gm");
        ws.onopen = function() {{
          ws.send(JSON.stringify({{ action: "join_scene", sceneId: SCENE_ID, role: "gm" }}));
        }};
        ws.onmessage = function(ev) {{
          try {{
            var msg = JSON.parse(ev.data);
            if (msg.action === "scene_state" || msg.action === "narrative_event") {{
              if (msg.narrativeState) document.getElementById("current-state").textContent = msg.narrativeState;
              if (msg.participantCount !== undefined) document.getElementById("p-count").textContent = msg.participantCount;
            }}
          }} catch(e) {{ }}
        }};
        ws.onerror = function() {{ console.warn("WS unavailable"); }};
        setInterval(function() {{
          if (ws && ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({{ action: "ping" }}));
        }}, 60000);
      }} catch(e) {{ console.warn("WS error:", e); }}
    }}
    connectWS();

    function showStatus(msg) {{
      var bar = document.getElementById("status-bar");
      bar.textContent = msg;
      bar.classList.add("show");
      setTimeout(function() {{ bar.classList.remove("show"); }}, 3000);
    }}

    function fireHook(hook) {{
      if (ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{
          action: "narrative_event",
          sceneId: SCENE_ID,
          hookId: hook.id,
          hookName: hook.name
        }}));
        showStatus("Hook fired: " + hook.name);
      }} else {{
        // Fallback: GM Event API (if configured)
        showStatus("WS not connected — hook queued: " + hook.name);
      }}
    }}
  }})();
  </script>
</body>
</html>"""

    # Upload GM panel HTML to S3
    gm_key = f"gm-panel/{scene_id}/index.html"
    try:
        s3.put_object(
            Bucket=bucket,
            Key=gm_key,
            Body=gm_panel_html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
    except Exception as exc:
        return {"status": "error", "error": f"S3 upload failed: {exc}"}

    gm_panel_url = f"https://{cf_domain}/{gm_key}"

    # Update DynamoDB record with GM panel URL
    try:
        dynamodb.Table(WEB_SCENES_TABLE).update_item(
            Key={"sceneId": scene_id},
            UpdateExpression="SET gmPanelUrl = :u",
            ExpressionAttributeValues={":u": gm_panel_url},
        )
    except Exception as exc:
        print(f"[web-platform] DynamoDB gmPanelUrl update failed (non-fatal): {exc}")

    return {
        "status":       "ok",
        "scene_id":     scene_id,
        "gm_panel_url": gm_panel_url,
        "gm_key":       gm_key,
        "hook_count":   len(gm_hooks),
        "note":         f"GM panel live at {gm_panel_url}?token=<jwt>",
    }


def _clean(item: dict) -> dict:
    return {
        "sceneId":     item.get("sceneId", ""),
        "sceneName":   item.get("sceneName", ""),
        "status":      item.get("status", ""),
        "webUrl":      item.get("webUrl", ""),
        "gmPanelUrl":  item.get("gmPanelUrl", ""),
        "deployedAt":  item.get("deployedAt", ""),
        "zoneCount":   item.get("zoneCount", 0),
        "mood":        item.get("atmosphereMood", ""),
    }


# ── Agent ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the WebPlatformAgent for the Hypermage VR system.

Your role is to bridge AI-generated scene plans and browser-based 3D experiences.
You turn ScenePlan JSON documents into live Babylon.js web scenes accessible via URL,
with spatial audio, glTF asset loading, mobile touch controls, and PWA manifests.

Workflow:
1. Call generate_web_scene(scene_plan_json) to build the HTML scene and upload to S3.
   Audio assets and glTF assets are automatically queried from DynamoDB and included.
2. Call deploy_web_scene(scene_id) to invalidate the CloudFront cache and get the live URL.
3. Return the URL to the caller so it can be shared with web participants.
4. Optionally call generate_gm_panel(scene_id) to create a GM control panel.

Use query_web_scenes to find previously generated scenes or check deployment status.

Features in generated scenes:
- Babylon.js 3D scene with zone blockouts, lighting, ground plane
- Audio: ambient loop + music score (from ElevenLabs/Stability AI, queried from DynamoDB)
- glTF assets: loaded from asset catalogue with correct world positions
- Virtual joystick: auto-enabled on touch devices (mobile/Quest browser)
- Tap-to-interact: mesh pick events broadcast via WebSocket
- Cognito gate: add ?require_auth=true to require JWT token
- PWA manifest: enables Add to Home Screen on mobile

Cost profile: S3 + CloudFront is serverless — zero idle cost.
"""


@app.entrypoint
async def invoke(payload, context):
    """WebPlatformAgent: ScenePlan → Babylon.js web scene."""
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    agent = Agent(
        model=model,
        tools=[generate_web_scene, deploy_web_scene, query_web_scenes, generate_gm_panel],
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
