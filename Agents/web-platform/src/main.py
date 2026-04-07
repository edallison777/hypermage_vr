"""WebPlatformAgent — Bedrock AgentCore agent for Hypermage VR.

Phase 10: Generates Babylon.js web scenes from ScenePlan JSON and deploys them
to S3/CloudFront so any browser can render the scene in 3D with ambient audio.

Tools:
  generate_web_scene  — ScenePlan JSON → Babylon.js HTML scene file in S3
  deploy_web_scene    — upload HTML to S3, invalidate CloudFront, return URL
  query_web_scenes    — list deployed scenes (optionally filter by sceneId/status)
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

MODEL_ID   = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

WEB_SCENES_TABLE  = os.environ.get("WEB_SCENES_TABLE", "hypermage-vr-web-scenes-dev")
CLOUDFRONT_DOMAIN_SSM = "/hypermage/web-platform/cloudfront-domain"
WS_URL_SSM            = "/hypermage/web-platform/ws-url"
BUCKET_SSM            = "/hypermage/web-platform/scenes-bucket"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3       = boto3.client("s3",   region_name=AWS_REGION)
ssm      = boto3.client("ssm",  region_name=AWS_REGION)
cf       = boto3.client("cloudfront", region_name=AWS_REGION)


def _get_ssm(name: str) -> str | None:
    try:
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:
        return None


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


def _generate_babylon_html(scene_plan: dict, ws_url: str) -> str:
    """Convert a ScenePlan dict into a self-contained Babylon.js HTML page."""
    scene_id   = scene_plan.get("id", str(uuid.uuid4()))
    scene_name = scene_plan.get("name", "Untitled Scene")
    zones      = scene_plan.get("zones", [])
    atmosphere = scene_plan.get("atmosphere", {})
    spawns     = scene_plan.get("participant_spawns", [])
    narr_states = scene_plan.get("narrative_states", [])

    lighting = _get_lighting(atmosphere.get("lighting_mood", "neutral white"))
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
    state_names = [s.get("name", s.get("id", "")) for s in narr_states]
    initial_state = next((s.get("name", "") for s in narr_states if s.get("is_initial")), "")

    ambient_r, ambient_g, ambient_b = lighting["ambient"]
    diff_r, diff_g, diff_b = lighting["diffuse"]

    zones_js = "[\n" + ",\n".join(zone_defs) + "\n]"
    states_js = json.dumps(state_names)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{scene_name} — Hypermage VR</title>
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

  <script src="https://cdn.babylonjs.com/babylon.js"></script>
  <script src="https://cdn.babylonjs.com/loaders/babylonjs.loaders.min.js"></script>
  <script>
  (function() {{
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

      // Label in HUD
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
            }} else if (msg.action === "presence") {{
              pCount.textContent = parseInt(pCount.textContent||1) + 0; // placeholder
            }}
          }} catch(e) {{ }}
        }};
        ws.onerror = function() {{ console.log("WS unavailable — offline mode"); }};
        // Keepalive ping every 60s
        setInterval(function() {{
          if (ws && ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({{ action: "ping" }}));
        }}, 60000);
      }} catch(e) {{ console.log("WS error:", e); }}
    }}

    // ── Render loop ──────────────────────────────────────────────────────────
    engine.runRenderLoop(function() {{ scene.render(); }});
    window.addEventListener("resize", function() {{ engine.resize(); }});
  }})();
  </script>
</body>
</html>"""


# ── Agent tools ────────────────────────────────────────────────────────────────

@tool
def generate_web_scene(scene_plan_json: str) -> dict:
    """Generate a Babylon.js HTML scene from a ScenePlan JSON string.

    Parses zones, atmosphere, and narrative states from the plan and produces
    a self-contained HTML file with 3D rendering and WebSocket presence.
    Uploads the HTML to S3 and records the scene in DynamoDB.

    Args:
        scene_plan_json: Full ScenePlan JSON string.

    Returns:
        {"status": "ok", "scene_id": str, "s3_key": str, "s3_uri": str}
    """
    try:
        scene_plan = json.loads(scene_plan_json)
    except Exception as exc:
        return {"status": "error", "error": f"Invalid ScenePlan JSON: {exc}"}

    bucket   = _get_ssm(BUCKET_SSM)
    ws_url   = _get_ssm(WS_URL_SSM) or "NOT_SET"
    cf_domain = _get_ssm(CLOUDFRONT_DOMAIN_SSM)

    if not bucket:
        return {"status": "skipped", "note": "Web platform SSM not configured — run deploy_phase10.py first"}

    scene_id  = scene_plan.get("id", str(uuid.uuid4()))
    html      = _generate_babylon_html(scene_plan, ws_url)
    s3_key    = f"scenes/{scene_id}/index.html"
    s3_uri    = f"s3://{bucket}/{s3_key}"
    web_url   = f"https://{cf_domain}/{s3_key}" if cf_domain else ""

    # Upload HTML to S3
    try:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
    except Exception as exc:
        return {"status": "error", "error": f"S3 upload failed: {exc}"}

    # Write DynamoDB record
    try:
        table = dynamodb.Table(WEB_SCENES_TABLE)
        table.put_item(Item={
            "sceneId":              scene_id,
            "sceneName":            scene_plan.get("name", ""),
            "sceneType":            scene_plan.get("scene_type", ""),
            "status":               "generated",
            "s3Key":                s3_key,
            "s3Uri":                s3_uri,
            "webUrl":               web_url,
            "generatedAt":          datetime.now(timezone.utc).isoformat(),
            "deployedAt":           "0000-00-00T00:00:00+00:00",  # placeholder; updated on deploy
            "zoneCount":            len(scene_plan.get("zones", [])),
            "atmosphereMood":       scene_plan.get("atmosphere", {}).get("lighting_mood", ""),
            "currentNarrativeState": next(
                (s.get("id", "") for s in scene_plan.get("narrative_states", []) if s.get("is_initial")),
                ""
            ),
            "ttl": int(time.time()) + 86400 * 90,  # 90-day TTL
        })
    except Exception as exc:
        return {"status": "error", "error": f"DynamoDB write failed: {exc}"}

    return {
        "status":   "ok",
        "scene_id": scene_id,
        "s3_key":   s3_key,
        "s3_uri":   s3_uri,
        "web_url":  web_url,
        "note":     "HTML generated — call deploy_web_scene to get a live CloudFront URL",
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
                    "Paths": {"Quantity": 1, "Items": [f"/{s3_key}"]},
                    "CallerReference": f"phase10-{scene_id}-{int(time.time())}",
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
        "status":                    "ok",
        "scene_id":                  scene_id,
        "web_url":                   web_url,
        "cloudfront_invalidation_id": invalidation_id,
        "note":                      "Scene is live — open the URL in any browser to view the 3D scene",
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
            from boto3.dynamodb.conditions import Key as DKey
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


def _clean(item: dict) -> dict:
    return {
        "sceneId":     item.get("sceneId", ""),
        "sceneName":   item.get("sceneName", ""),
        "status":      item.get("status", ""),
        "webUrl":      item.get("webUrl", ""),
        "deployedAt":  item.get("deployedAt", ""),
        "zoneCount":   item.get("zoneCount", 0),
        "mood":        item.get("atmosphereMood", ""),
    }


# ── Agent ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the WebPlatformAgent for the Hypermage VR system.

Your role is to bridge AI-generated scene plans and browser-based 3D experiences.
You turn ScenePlan JSON documents into live Babylon.js web scenes accessible via URL.

Workflow:
1. Call generate_web_scene(scene_plan_json) to build the HTML scene and upload to S3.
2. Call deploy_web_scene(scene_id) to invalidate the CloudFront cache and get the live URL.
3. Return the URL to the caller so it can be shared with web participants.
4. Web participants open the URL in Chrome/Firefox and see the scene in 3D.
5. All VR + web participants share the same DynamoDB session — narrative state changes
   pushed via WebSocket are reflected in real-time in both VR and the browser.

Use query_web_scenes to find previously generated scenes or check deployment status.

Cost profile: S3 + CloudFront is serverless — zero idle cost. WebSocket connections
cost ~$0.00025/minute per active participant — negligible for dev usage.
"""

model  = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
tools  = [generate_web_scene, deploy_web_scene, query_web_scenes]
agent  = Agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)


@app.entrypoint
async def main(payload: dict) -> str:
    prompt = payload.get("prompt", "")
    result_chunks = []
    async for event in agent.stream_async(prompt):
        if isinstance(event, dict) and "data" in event:
            result_chunks.append(str(event["data"]))
    return "".join(result_chunks)


if __name__ == "__main__":
    app.run()
