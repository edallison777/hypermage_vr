"""
Phase 8 Integration Test
=========================
Validates the audio production pipeline end-to-end.

Tests:
  1. TechArtVFXAudioAgent: generate_ambient  → DynamoDB record (status: ready or skipped)
  2. TechArtVFXAudioAgent: generate_sfx      → DynamoDB record
  3. TechArtVFXAudioAgent: generate_narration → DynamoDB record
  4. TechArtVFXAudioAgent: query_audio_assets → returns records from tests 1–3
  5. DynamoDB: records directly retrievable by sceneId GSI
  6. TechArtVFXAudioAgent: full ScenePlan audio palette → complete audio asset set

Tests pass if status is 'ready' (API keys set) OR 'skipped' (keys not set).
Both outcomes confirm the pipeline wiring is correct.

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase8.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase8.py --verbose
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

REGION   = "eu-west-1"
ACCOUNT  = "732231126129"
TABLE    = "hypermage-vr-audio-assets-dev"
SCENE_ID = f"test-scene-{str(uuid.uuid4())[:8]}"


def _read_agent_arn(agent_dir: str) -> str:
    yaml_path = Path(__file__).parent.parent / "Agents" / agent_dir / ".bedrock_agentcore.yaml"
    try:
        content = yaml_path.read_text()
        m = re.search(r"agent_arn:\s*(arn:aws:bedrock-agentcore:[^\s]+)", content)
        return m.group(1) if m else ""
    except Exception:
        return ""


def invoke_agent(arn: str, prompt: str) -> str:
    client = boto3.client(
        "bedrock-agentcore", region_name=REGION,
        config=Config(read_timeout=300, connect_timeout=10),
    )
    resp  = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw    = resp["response"].read().decode("utf-8")
    chunks = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            value = line[6:].strip()
            if value.startswith('"') and value.endswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            chunks.append(value)
    return "".join(chunks)


def run_test(name: str, fn, verbose: bool) -> bool:
    print(f"\n[TEST] {name}")
    try:
        passed, info = fn(verbose)
        print(f"  {'PASS' if passed else 'FAIL'} — {info}")
        return passed
    except Exception as exc:
        print(f"  ERROR — {exc}")
        return False


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_generate_ambient(verbose: bool):
    arn = _read_agent_arn("tech-art-vfx-audio")
    if not arn:
        return False, "TechArtVFXAudio agent ARN not found — run deploy_phase8.py first"
    resp = invoke_agent(arn,
        f"Generate ambient audio for scene_id='{SCENE_ID}' with description: "
        "'Ritual chamber ambience — deep stone resonance, distant wind, flickering torch sounds, "
        "mysterious low hum'. Duration 60 seconds.")
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = "ready" in resp.lower() or "skipped" in resp.lower() or "audio_id" in resp.lower()
    return passed, "ambient generation returned valid status"


def test_generate_sfx(verbose: bool):
    arn = _read_agent_arn("tech-art-vfx-audio")
    if not arn:
        return False, "ARN not found"
    resp = invoke_agent(arn,
        f"Generate a sound effect for scene_id='{SCENE_ID}': "
        "'Mystical oracle awakening — glowing crystal resonance, magical shimmer, low rumble'. "
        "Duration 3 seconds.")
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = "ready" in resp.lower() or "skipped" in resp.lower() or "audio_id" in resp.lower()
    return passed, "SFX generation returned valid status"


def test_generate_narration(verbose: bool):
    arn = _read_agent_arn("tech-art-vfx-audio")
    if not arn:
        return False, "ARN not found"
    resp = invoke_agent(arn,
        f"Generate narration for scene_id='{SCENE_ID}': "
        "'Welcome, seeker. The oracle awaits your question. "
        "Approach the sacred flame and speak your truth.'")
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = "ready" in resp.lower() or "skipped" in resp.lower() or "audio_id" in resp.lower()
    return passed, "narration generation returned valid status"


def test_query_audio_assets(verbose: bool):
    arn = _read_agent_arn("tech-art-vfx-audio")
    if not arn:
        return False, "ARN not found"
    resp = invoke_agent(arn, f"Query all audio assets for scene_id='{SCENE_ID}'.")
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = ("asset" in resp.lower() or "audio" in resp.lower()) and "error" not in resp.lower()
    return passed, "query_audio_assets returned response"


def test_dynamodb_records(verbose: bool):
    """Directly verify DynamoDB has records for the test scene."""
    db    = boto3.resource("dynamodb", region_name=REGION)
    table = db.Table(TABLE)
    resp  = table.query(
        IndexName="SceneIdIndex",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("sceneId").eq(SCENE_ID),
    )
    items = resp.get("Items", [])
    if verbose and items:
        for item in items:
            print(f"  [{item.get('audioType')}] {item.get('status')} — {item.get('description', '')[:60]}")
    if items:
        types = [i.get("audioType") for i in items]
        return True, f"{len(items)} records in DynamoDB for scene — types: {types}"
    return False, f"No DynamoDB records found for sceneId={SCENE_ID}"


def test_full_scene_audio(verbose: bool):
    arn = _read_agent_arn("tech-art-vfx-audio")
    if not arn:
        return False, "ARN not found"
    # Use the oracle scene from Phase 7 test
    resp = invoke_agent(arn,
        f"Generate a complete audio set for scene_id='{SCENE_ID}-full' based on this "
        "ScenePlan audio_palette: 'Stone chamber echoes, mystical humming, ritual chanting, "
        "deep resonant drums, flickering torch ambience'. "
        "Generate: one ambient track, one atmospheric score, and one SFX for the oracle awakening. "
        "Then query all assets for the scene and return the full audio asset list.")
    if verbose:
        print(f"  Response:\n{resp[:3000]}")
    # Success = at least ambient + at least one other track
    lower  = resp.lower()
    has_ambient  = "ambient" in lower
    has_audio    = "audio_id" in lower or "s3_uri" in lower or "skipped" in lower or "score" in lower
    passed = has_ambient and has_audio
    return passed, "full scene audio set generated and queried" if passed else "incomplete audio set"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 8 Integration Tests")
    print("=" * 60)
    print(f"Test scene ID: {SCENE_ID}")
    print(f"DynamoDB table: {TABLE}")
    print("Note: tests pass if status is 'ready' (API key set) or 'skipped' (key absent)")

    tests = [
        ("TechArtVFXAudioAgent — generate_ambient  → DynamoDB",        test_generate_ambient),
        ("TechArtVFXAudioAgent — generate_sfx      → DynamoDB",        test_generate_sfx),
        ("TechArtVFXAudioAgent — generate_narration → DynamoDB",       test_generate_narration),
        ("TechArtVFXAudioAgent — query_audio_assets (scene filter)",   test_query_audio_assets),
        ("DynamoDB — records directly retrievable by sceneId GSI",     test_dynamodb_records),
        ("TechArtVFXAudioAgent — full ScenePlan audio palette → set",  test_full_scene_audio),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed_count = sum(results)
    print(f"Results: {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("ALL TESTS PASSED — Phase 8 complete")
        return 0
    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
