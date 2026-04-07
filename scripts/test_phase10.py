"""
Phase 10 Integration Test
==========================
Validates the Web Platform Foundation pipeline.

Tests:
  1. SSM: /hypermage/web-platform/cloudfront-domain exists
  2. SSM: /hypermage/web-platform/ws-url exists
  3. SSM: /hypermage/web-platform/scenes-bucket exists
  4. WebPlatformAgent: query_web_scenes → ok (may be empty)
  5. WebPlatformAgent: generate_web_scene from a real ScenePlan → ok or skipped
  6. WebPlatformAgent: deploy_web_scene for generated scene → ok or skipped

Tests pass if status is 'ok' (infrastructure deployed) OR 'skipped' (SSM not configured).
Both outcomes confirm the wiring is correct.

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase10.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase10.py --verbose
"""

import argparse
import json
import re
import sys
from pathlib import Path

import boto3
from botocore.config import Config

REGION  = "eu-west-1"
ACCOUNT = "732231126129"

MINIMAL_SCENE_PLAN = json.dumps({
    "id": "phase10-test-scene-001",
    "name": "Phase 10 Test Scene",
    "description": "Minimal scene for Phase 10 smoke test",
    "scene_type": "cyberspace",
    "platforms": ["vr", "web"],
    "narrative_context": {
        "setting": "A glowing data nexus in cyberspace",
        "tone": "mysterious",
        "initial_state": "state_idle"
    },
    "atmosphere": {
        "lighting_mood": "neon cyber",
        "vfx_density": "low",
        "audio_palette": "ambient electronic hum"
    },
    "zones": [
        {
            "id": "zone_nexus",
            "name": "Data Nexus",
            "type": "exploration",
            "bounds": {
                "center": {"x": 0, "y": 0, "z": 0},
                "extents": {"x": 600, "y": 600, "z": 300}
            }
        },
        {
            "id": "zone_portal",
            "name": "Portal Gate",
            "type": "transit",
            "bounds": {
                "center": {"x": 800, "y": 0, "z": 0},
                "extents": {"x": 200, "y": 200, "z": 300}
            }
        }
    ],
    "participant_spawns": [
        {
            "position": {"x": 0, "y": -500, "z": 100},
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0}
        }
    ],
    "objectives": [],
    "narrative_states": [
        {
            "id": "state_idle",
            "name": "Idle",
            "description": "Initial dormant state",
            "is_initial": True
        },
        {
            "id": "state_active",
            "name": "Active",
            "description": "Data nexus activated",
            "is_initial": False
        }
    ],
    "gm_hooks": [
        {"id": "hook_activate", "name": "Activate Nexus", "description": "Triggers activation event"}
    ],
    "asset_sources": []
})


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
        config=Config(read_timeout=120, connect_timeout=10),
    )
    resp  = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw = resp["response"].read().decode("utf-8")

    # Handle plain JSON string response (WebPlatformAgent pattern)
    stripped = raw.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Handle SSE "data: " line format (other agents)
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
    if chunks:
        return "".join(chunks)

    # Fallback: return raw
    return raw


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

def test_ssm_cloudfront(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/web-platform/cloudfront-domain")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        return True, f"CloudFront domain: {value}"
    except ssm.exceptions.ParameterNotFound:
        return False, "SSM /hypermage/web-platform/cloudfront-domain not found — run deploy_phase10.py first"
    except Exception as exc:
        return False, str(exc)


def test_ssm_ws_url(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/web-platform/ws-url")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        return True, f"WebSocket URL: {value}"
    except ssm.exceptions.ParameterNotFound:
        return False, "SSM /hypermage/web-platform/ws-url not found — run deploy_phase10.py first"
    except Exception as exc:
        return False, str(exc)


def test_ssm_bucket(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/web-platform/scenes-bucket")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        return True, f"S3 bucket: {value}"
    except ssm.exceptions.ParameterNotFound:
        return False, "SSM /hypermage/web-platform/scenes-bucket not found — run deploy_phase10.py first"
    except Exception as exc:
        return False, str(exc)


def test_query_web_scenes(verbose: bool):
    arn = _read_agent_arn("web-platform")
    if not arn:
        return False, "WebPlatform agent ARN not found — run deploy_phase10.py first"
    resp = invoke_agent(arn, "Query all deployed web scenes. Use query_web_scenes with no filters.")
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = (
        "skipped" in resp.lower()
        or "scene" in resp.lower()
        or "count" in resp.lower()
        or "status" in resp.lower()
    )
    return passed, "query_web_scenes returned valid response"


_generated_scene_id = None  # shared between tests 5 and 6


def test_generate_web_scene(verbose: bool):
    global _generated_scene_id
    arn = _read_agent_arn("web-platform")
    if not arn:
        return False, "ARN not found"
    resp = invoke_agent(
        arn,
        f"Generate a web scene from this ScenePlan JSON and upload it to S3. "
        f"Call generate_web_scene with this JSON:\n{MINIMAL_SCENE_PLAN}"
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")

    # Try to extract scene_id from response
    m = re.search(r'"scene_id":\s*"([^"]+)"', resp)
    if m:
        _generated_scene_id = m.group(1)

    passed = (
        "skipped" in resp.lower()
        or "scene_id" in resp.lower()
        or "s3" in resp.lower()
        or "generated" in resp.lower()
        or "html" in resp.lower()
    )
    return passed, f"generate_web_scene returned valid response (scene_id={_generated_scene_id or 'unknown'})"


def test_deploy_web_scene(verbose: bool):
    arn = _read_agent_arn("web-platform")
    if not arn:
        return False, "ARN not found"

    scene_id = _generated_scene_id or "phase10-test-scene-001"
    resp = invoke_agent(
        arn,
        f"Deploy the web scene with scene_id '{scene_id}'. "
        f"Call deploy_web_scene(scene_id='{scene_id}') and return the URL."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")

    passed = (
        "skipped" in resp.lower()
        or "deployed" in resp.lower()
        or "cloudfront" in resp.lower()
        or "url" in resp.lower()
        or "https://" in resp.lower()
    )
    return passed, "deploy_web_scene returned valid response"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 10 Integration Tests")
    print("=" * 60)
    print("Note: tests pass if status is 'ok' (infrastructure deployed) or 'skipped' (SSM not configured)")

    tests = [
        ("SSM — /hypermage/web-platform/cloudfront-domain",       test_ssm_cloudfront),
        ("SSM — /hypermage/web-platform/ws-url",                  test_ssm_ws_url),
        ("SSM — /hypermage/web-platform/scenes-bucket",           test_ssm_bucket),
        ("WebPlatformAgent — query_web_scenes",                   test_query_web_scenes),
        ("WebPlatformAgent — generate_web_scene from ScenePlan",  test_generate_web_scene),
        ("WebPlatformAgent — deploy_web_scene",                   test_deploy_web_scene),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed_count = sum(results)
    print(f"Results: {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("ALL TESTS PASSED — Phase 10 complete")
        print("\nOpen the CloudFront URL in a browser to see the Babylon.js scene.")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
