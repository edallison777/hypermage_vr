"""TechArtVFXAudioAgent — AI audio production for Hypermage VR/Web scenes.

Phase 8: Real audio generation tools.
  - generate_ambient:    Stability AI → ambient loop MP3 → S3 + DynamoDB
  - generate_score:      Stability AI → music score MP3 → S3 + DynamoDB
  - generate_sfx:        ElevenLabs Sound Effects → SFX MP3 → S3 + DynamoDB
  - generate_narration:  ElevenLabs TTS → narration MP3 → S3 + DynamoDB
  - query_audio_assets:  DynamoDB query by scene_id or audio_type

API keys read from SSM. All tools skip gracefully (status='skipped') if keys
are absent — zero cost when not configured. No idle compute.

Audio stored at: s3://{bucket}/audio/generated/{scene_id}/{type}/{audio_id}.mp3
"""

import json
import os
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MODEL_ID    = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION  = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
S3_BUCKET   = os.environ.get("BUILD_S3_BUCKET", "hypermage-vr-unreal-build-artifacts-dev")
AUDIO_TABLE = os.environ.get("AUDIO_ASSETS_TABLE", "hypermage-vr-audio-assets-dev")
EL_KEY_PATH = os.environ.get("ELEVENLABS_KEY_SSM", "/hypermage/elevenlabs-api-key")
ST_KEY_PATH = os.environ.get("STABILITY_KEY_SSM",  "/hypermage/stability-api-key")

# Default ElevenLabs voice for narration (Rachel — warm, clear)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

ssm      = boto3.client("ssm", region_name=AWS_REGION)
s3       = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

_key_cache: dict[str, str | None] = {}


def _get_ssm_key(path: str) -> str | None:
    """Read an API key from SSM. Returns None if absent or set to NOT_SET."""
    if path in _key_cache:
        return _key_cache[path]
    try:
        resp  = ssm.get_parameter(Name=path, WithDecryption=True)
        value = resp["Parameter"]["Value"]
        result = None if value in ("NOT_SET", "", "PLACEHOLDER") else value
    except ssm.exceptions.ParameterNotFound:
        result = None
    except Exception as exc:
        print(f"[audio] SSM {path} error: {exc}")
        result = None
    _key_cache[path] = result
    return result


def _write_audio_record(audio_id: str, scene_id: str, audio_type: str,
                        description: str, status: str, s3_uri: str = "",
                        duration: float = 0.0, note: str = "",
                        generation_params: dict | None = None) -> None:
    """Write or update an audio asset record in DynamoDB."""
    now  = datetime.now(timezone.utc).isoformat()
    item = {
        "audioId":   audio_id,
        "sceneId":   scene_id or "unassigned",
        "audioType": audio_type,
        "status":    status,
        "description": description,
        "createdAt": now,
        "updatedAt": now,
    }
    if s3_uri:
        item["s3Uri"] = s3_uri
    if duration:
        item["duration"] = str(duration)
    if note:
        item["statusNote"] = note
    if generation_params:
        item["generationParams"] = json.dumps(generation_params)
    dynamodb.Table(AUDIO_TABLE).put_item(Item=item)


def _http_post(url: str, headers: dict, body: bytes | None = None) -> bytes:
    """Simple HTTP POST, returns response body bytes."""
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _upload_audio(audio_bytes: bytes, s3_key: str, content_type: str = "audio/mpeg") -> str:
    """Upload audio bytes to S3 and return the s3:// URI."""
    s3.put_object(
        Bucket=S3_BUCKET, Key=s3_key,
        Body=audio_bytes, ContentType=content_type,
    )
    return f"s3://{S3_BUCKET}/{s3_key}"


# ── Stability AI helpers ──────────────────────────────────────────────────────

def _stability_generate_audio(prompt: str, duration: float, api_key: str) -> bytes:
    """
    Call Stability AI Stable Audio API.
    POST https://api.stability.ai/v2beta/stable-audio
    Returns MP3 bytes.
    """
    url   = "https://api.stability.ai/v2beta/stable-audio"
    body  = json.dumps({
        "prompt":           prompt,
        "output_format":    "mp3",
        "duration":         duration,
    }).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "audio/mpeg",
    }
    return _http_post(url, headers, body)


# ── ElevenLabs helpers ────────────────────────────────────────────────────────

def _elevenlabs_sfx(description: str, duration: float, api_key: str) -> bytes:
    """
    Call ElevenLabs Sound Generation API.
    POST https://api.elevenlabs.io/v1/sound-generation
    Returns MP3 bytes.
    """
    url  = "https://api.elevenlabs.io/v1/sound-generation"
    body = json.dumps({
        "text":             description,
        "duration_seconds": min(duration, 22.0),  # ElevenLabs max 22s
        "prompt_influence": 0.3,
    }).encode()
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
    }
    return _http_post(url, headers, body)


def _elevenlabs_tts(text: str, voice_id: str, api_key: str) -> bytes:
    """
    Call ElevenLabs TTS API.
    POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
    Returns MP3 bytes.
    """
    url  = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = json.dumps({
        "text":     text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    return _http_post(url, headers, body)


# ── Agent Tools ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the TechArtVFXAudioAgent for Hypermage — responsible for
AI-generated audio production: ambient soundscapes, music scores, sound effects, and narration.

Your responsibilities:
1. Ambient audio: generate looping atmospheric soundscapes from ScenePlan audio_palette descriptions
2. Music scores: generate dramatic, atmospheric music matching the scene tone
3. SFX: generate short sound effects for GM hooks, objectives, and VFX triggers
4. Narration: generate NPC speech and narrator voice-over from script text
5. Quest 3 optimisation: confirm audio within limits (max 32 concurrent, OGG/MP3 compressed)

When given a ScenePlan or audio request:
1. Call generate_ambient() for the overall atmospheric soundscape
2. Call generate_score() for background music
3. Call generate_sfx() for each GM hook that needs a sound cue
4. Call generate_narration() for any scripted speech
5. Call query_audio_assets(scene_id) to return the full audio asset set
6. Return S3 URIs and a summary for the UE5/web pipeline to consume

API keys are read from SSM. If not configured, tools skip gracefully with status='skipped'.
Configure keys:
  aws ssm put-parameter --name /hypermage/elevenlabs-api-key --value YOUR_KEY --type SecureString
  aws ssm put-parameter --name /hypermage/stability-api-key  --value YOUR_KEY --type SecureString"""


@tool
def generate_ambient(scene_id: str, description: str, duration: float = 60.0) -> str:
    """Generate an ambient soundscape loop from a text description using Stability AI.
    Stores MP3 at s3://{bucket}/audio/generated/{scene_id}/ambient/{audio_id}.mp3
    Returns {status, audio_id, s3_uri, duration} JSON."""
    audio_id   = str(uuid.uuid4())
    api_key    = _get_ssm_key(ST_KEY_PATH)
    audio_type = "ambient"

    if not api_key:
        _write_audio_record(audio_id, scene_id, audio_type, description, "skipped",
                            note="Stability AI key not set. Configure /hypermage/stability-api-key in SSM.")
        return json.dumps({"status": "skipped", "audio_id": audio_id,
                           "note": "Set /hypermage/stability-api-key in SSM to enable ambient generation."})

    try:
        print(f"[audio] Generating ambient: {description[:60]}...")
        audio_bytes = _stability_generate_audio(
            f"Ambient soundscape loop: {description}. Seamless loop, no sudden transitions.",
            duration, api_key,
        )
        s3_key  = f"audio/generated/{scene_id}/{audio_type}/{audio_id}.mp3"
        s3_uri  = _upload_audio(audio_bytes, s3_key)
        _write_audio_record(audio_id, scene_id, audio_type, description, "ready",
                            s3_uri=s3_uri, duration=duration,
                            generation_params={"provider": "stability-ai", "duration": duration})
        print(f"[audio] Ambient saved: {s3_key} ({len(audio_bytes)} bytes)")
        return json.dumps({"status": "ready", "audio_id": audio_id,
                           "s3_uri": s3_uri, "duration": duration, "type": audio_type})
    except Exception as exc:
        _write_audio_record(audio_id, scene_id, audio_type, description, "error",
                            note=str(exc))
        return json.dumps({"status": "error", "audio_id": audio_id, "error": str(exc)})


@tool
def generate_score(scene_id: str, description: str, duration: float = 120.0,
                   loop: bool = True) -> str:
    """Generate a music score from a text description using Stability AI.
    Stores MP3 at s3://{bucket}/audio/generated/{scene_id}/score/{audio_id}.mp3
    Returns {status, audio_id, s3_uri, duration} JSON."""
    audio_id   = str(uuid.uuid4())
    api_key    = _get_ssm_key(ST_KEY_PATH)
    audio_type = "score"

    if not api_key:
        _write_audio_record(audio_id, scene_id, audio_type, description, "skipped",
                            note="Stability AI key not set.")
        return json.dumps({"status": "skipped", "audio_id": audio_id,
                           "note": "Set /hypermage/stability-api-key in SSM to enable score generation."})

    try:
        loop_hint = " Seamless loop with smooth intro and outro." if loop else ""
        print(f"[audio] Generating score: {description[:60]}...")
        audio_bytes = _stability_generate_audio(
            f"Original music score: {description}.{loop_hint}",
            duration, api_key,
        )
        s3_key  = f"audio/generated/{scene_id}/{audio_type}/{audio_id}.mp3"
        s3_uri  = _upload_audio(audio_bytes, s3_key)
        _write_audio_record(audio_id, scene_id, audio_type, description, "ready",
                            s3_uri=s3_uri, duration=duration,
                            generation_params={"provider": "stability-ai", "duration": duration, "loop": loop})
        print(f"[audio] Score saved: {s3_key} ({len(audio_bytes)} bytes)")
        return json.dumps({"status": "ready", "audio_id": audio_id,
                           "s3_uri": s3_uri, "duration": duration, "type": audio_type})
    except Exception as exc:
        _write_audio_record(audio_id, scene_id, audio_type, description, "error",
                            note=str(exc))
        return json.dumps({"status": "error", "audio_id": audio_id, "error": str(exc)})


@tool
def generate_sfx(scene_id: str, description: str, duration: float = 3.0) -> str:
    """Generate a short sound effect using ElevenLabs Sound Generation API.
    Stores MP3 at s3://{bucket}/audio/generated/{scene_id}/sfx/{audio_id}.mp3
    Returns {status, audio_id, s3_uri} JSON."""
    audio_id   = str(uuid.uuid4())
    api_key    = _get_ssm_key(EL_KEY_PATH)
    audio_type = "sfx"

    if not api_key:
        _write_audio_record(audio_id, scene_id, audio_type, description, "skipped",
                            note="ElevenLabs key not set.")
        return json.dumps({"status": "skipped", "audio_id": audio_id,
                           "note": "Set /hypermage/elevenlabs-api-key in SSM to enable SFX generation."})

    try:
        print(f"[audio] Generating SFX: {description[:60]}...")
        audio_bytes = _elevenlabs_sfx(description, duration, api_key)
        s3_key  = f"audio/generated/{scene_id}/{audio_type}/{audio_id}.mp3"
        s3_uri  = _upload_audio(audio_bytes, s3_key)
        _write_audio_record(audio_id, scene_id, audio_type, description, "ready",
                            s3_uri=s3_uri, duration=duration,
                            generation_params={"provider": "elevenlabs-sfx", "duration": duration})
        print(f"[audio] SFX saved: {s3_key} ({len(audio_bytes)} bytes)")
        return json.dumps({"status": "ready", "audio_id": audio_id,
                           "s3_uri": s3_uri, "duration": duration, "type": audio_type})
    except Exception as exc:
        _write_audio_record(audio_id, scene_id, audio_type, description, "error",
                            note=str(exc))
        return json.dumps({"status": "error", "audio_id": audio_id, "error": str(exc)})


@tool
def generate_narration(scene_id: str, text: str, voice_id: str = DEFAULT_VOICE_ID) -> str:
    """Generate spoken narration using ElevenLabs TTS.
    Stores MP3 at s3://{bucket}/audio/generated/{scene_id}/narration/{audio_id}.mp3
    Returns {status, audio_id, s3_uri, character_count} JSON.
    Default voice: Rachel (warm, clear). Set voice_id for a different ElevenLabs voice."""
    audio_id   = str(uuid.uuid4())
    api_key    = _get_ssm_key(EL_KEY_PATH)
    audio_type = "narration"

    if not api_key:
        _write_audio_record(audio_id, scene_id, audio_type, text[:100], "skipped",
                            note="ElevenLabs key not set.")
        return json.dumps({"status": "skipped", "audio_id": audio_id,
                           "note": "Set /hypermage/elevenlabs-api-key in SSM to enable narration."})

    try:
        print(f"[audio] Generating narration: {text[:60]}...")
        audio_bytes = _elevenlabs_tts(text, voice_id, api_key)
        s3_key  = f"audio/generated/{scene_id}/{audio_type}/{audio_id}.mp3"
        s3_uri  = _upload_audio(audio_bytes, s3_key)
        _write_audio_record(audio_id, scene_id, audio_type, text[:200], "ready",
                            s3_uri=s3_uri,
                            generation_params={"provider": "elevenlabs-tts", "voice_id": voice_id,
                                               "character_count": len(text)})
        print(f"[audio] Narration saved: {s3_key} ({len(audio_bytes)} bytes)")
        return json.dumps({"status": "ready", "audio_id": audio_id,
                           "s3_uri": s3_uri, "character_count": len(text), "type": audio_type})
    except Exception as exc:
        _write_audio_record(audio_id, scene_id, audio_type, text[:100], "error",
                            note=str(exc))
        return json.dumps({"status": "error", "audio_id": audio_id, "error": str(exc)})


@tool
def query_audio_assets(scene_id: str = "", audio_type: str = "", limit: int = 50) -> str:
    """Query generated audio assets from DynamoDB.
    Filter by scene_id or audio_type (ambient/score/sfx/narration).
    Returns list of audio records with S3 URIs."""
    table = dynamodb.Table(AUDIO_TABLE)
    try:
        if scene_id:
            resp = table.query(
                IndexName="SceneIdIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("sceneId").eq(scene_id),
                Limit=limit,
            )
        elif audio_type:
            resp = table.query(
                IndexName="AudioTypeIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("audioType").eq(audio_type),
                Limit=limit,
            )
        else:
            resp = table.scan(Limit=limit)

        items = resp.get("Items", [])
        return json.dumps({
            "status": "ok",
            "count":  len(items),
            "assets": items,
            "filters": {"scene_id": scene_id, "audio_type": audio_type},
        }, default=str)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def generate_tier1_asset(concept_art_path: str, asset_type: str) -> str:
    """Generate a Tier 1 placeholder asset from 2D concept art. Use AssetPipelineAgent for
    full provenance tracking; this is a quick preview generator."""
    return json.dumps({
        "status":  "delegated",
        "message": "For full asset generation with provenance, use AssetPipelineAgent.validate_asset_import + create_provenance_record.",
        "concept_art": concept_art_path,
        "asset_type":  asset_type,
    })


@tool
def implement_niagara_vfx(effect_type: str, target_fps: int = 72) -> str:
    """Return particle budgets and Niagara configuration guidance for the given effect type
    within Quest 3 framerate constraints."""
    budgets = {72: 200, 90: 100, 120: 50}
    budget  = budgets.get(target_fps, 200)
    return json.dumps({
        "effect_type":      effect_type,
        "target_fps":       target_fps,
        "max_particles":    budget,
        "recommendations":  [
            f"Max {budget} GPU particles at {target_fps}FPS on Quest 3 (Snapdragon XR2 Gen 2)",
            "Use GPU simulation module, not CPU",
            "Simple lit material (no translucency stacking)",
            "Cull distance: 2000-5000 UU depending on effect size",
            "Avoid overdraw — use mesh emitters for large VFX",
        ],
    })


@tool
def configure_spatial_audio(audio_asset: str, attenuation_distance: float = 2000.0) -> str:
    """Return spatial audio configuration for a Quest 3 audio asset with HRTF settings."""
    return json.dumps({
        "audio_asset":          audio_asset,
        "attenuation_type":     "logarithmic",
        "inner_radius":         attenuation_distance * 0.1,
        "falloff_distance":     attenuation_distance,
        "hrtf":                 True,
        "spatialization_method": "binaural",
        "max_concurrent":       32,
        "compression":          "OGG Vorbis q6 (approx 192kbps)",
        "note": (
            "Quest 3: max 32 concurrent sounds. Use sound classes to prioritise. "
            "Compress all audio to OGG. Mono for positional, stereo for music/ambient."
        ),
    })


@tool
def optimize_for_quest3(scene_stats: str) -> str:
    """Analyse scene stats and return Quest 3 optimisation recommendations."""
    return json.dumps({
        "targets": {
            "draw_calls":     "< 100 per frame",
            "triangles":      "< 100k per frame",
            "texture_memory": "< 512MB total",
            "dynamic_lights": "1-2 max",
            "audio_sources":  "32 max concurrent",
            "vfx_particles":  "200 max @ 72FPS",
        },
        "recommendations": [
            "ASTC texture compression (4x4 block, LDR for colour, HDR for normals)",
            "LOD0/LOD1/LOD2 at 100%, 50%, 25% polygon counts",
            "Use mobile-friendly materials: no layered materials, no subsurface scattering",
            "Merge static meshes where possible to reduce draw calls",
            "Occlusion culling: set reasonable Cull Distance Volumes per zone",
            "VFX: GPU particles only, budget per zone (see implement_niagara_vfx)",
            "Audio: compress to OGG, use Sound Cue distance culling",
        ],
        "input_stats": scene_stats,
    })


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def invoke(payload, context):
    """TechArtVFXAudioAgent: audio production + VFX guidance for Hypermage scenes."""
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        tools=[
            generate_ambient, generate_score, generate_sfx, generate_narration,
            query_audio_assets,
            generate_tier1_asset, implement_niagara_vfx,
            configure_spatial_audio, optimize_for_quest3,
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
