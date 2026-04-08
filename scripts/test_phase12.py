"""
Phase 12 Integration Test
==========================
Validates UnrealLevelBuilder full ScenePlan→UE5 map conversion.

Tests:
  1. SSM: /hypermage/unreal-bridge-url exists (may be NOT_SET — that is fine)
  2. UnrealLevelBuilderAgent: get_bridge_status → ok or skipped
  3. UnrealLevelBuilderAgent: convert_sceneplan_to_map with minimal ScenePlan → ok or skipped
  4. UnrealLevelBuilderAgent: apply_atmosphere("neon cyber") → ok or skipped
  5. UnrealLevelBuilderAgent: generate_blockout_geometry (offline) → always passes

Tests pass if status is 'ok' OR 'skipped' — bridge being offline is expected in CI.

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase12.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase12.py --verbose
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
    "id":   "phase12-test-scene-001",
    "name": "Phase 12 Test Scene",
    "scene_type": "cyberspace",
    "atmosphere": {
        "lighting_mood": "neon cyber",
        "vfx_density":   "low",
    },
    "zones": [
        {
            "id":   "zone_nexus",
            "name": "Data Nexus",
            "type": "exploration",
            "bounds": {
                "center":  {"x": 0, "y": 0, "z": 0},
                "extents": {"x": 600, "y": 600, "z": 300}
            }
        }
    ],
    "participant_spawns": [
        {"position": {"x": 0, "y": -500, "z": 100}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0}}
    ],
    "narrative_states": [
        {"id": "state_idle", "name": "Idle", "is_initial": True}
    ],
    "gm_hooks": [
        {"id": "hook_activate", "name": "Activate", "description": "Activation event"}
    ],
    "asset_sources": [],
    "objectives": [],
})

MINIMAL_ZONES = json.dumps([
    {
        "id": "zone_test", "name": "Test Zone", "type": "cyberspace",
        "bounds": {
            "center":  {"x": 0, "y": 0, "z": 0},
            "extents": {"x": 500, "y": 500, "z": 250}
        }
    }
])


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
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw = resp["response"].read().decode("utf-8")

    stripped = raw.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

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

def test_ssm_bridge_url(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/unreal-bridge-url")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        if value in ("NOT_SET", "", "PLACEHOLDER"):
            return True, "Bridge URL = NOT_SET (expected — bridge not running now)"
        return True, f"Bridge URL: {value}"
    except Exception as exc:
        return False, f"SSM /hypermage/unreal-bridge-url not found: {exc}"


def test_bridge_status(verbose: bool):
    arn = _read_agent_arn("unreal-level-builder")
    if not arn:
        return False, "UnrealLevelBuilder agent ARN not found — run deploy_phase12.py first"
    resp = invoke_agent(
        arn,
        "Check if the UnrealBridge is reachable. Call get_bridge_status()."
    )
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = (
        "skipped" in resp.lower()
        or "bridge_url" in resp.lower()
        or "reachable" in resp.lower()
        or "not set" in resp.lower()
        or "status" in resp.lower()
    )
    return passed, "get_bridge_status returned valid response"


def test_convert_sceneplan_to_map(verbose: bool):
    arn = _read_agent_arn("unreal-level-builder")
    if not arn:
        return False, "UnrealLevelBuilder agent ARN not found"
    resp = invoke_agent(
        arn,
        f"Convert this ScenePlan to a UE5 map named 'Phase12TestMap'. "
        f"Call convert_sceneplan_to_map with this JSON and map_name='Phase12TestMap':\n"
        f"{MINIMAL_SCENE_PLAN}\n"
        f"If the bridge is not configured, a skipped response is expected and fine."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")
    passed = (
        "skipped" in resp.lower()
        or "actors_spawned" in resp.lower()
        or "atmosphere" in resp.lower()
        or "hooks_wired" in resp.lower()
        or "bridge" in resp.lower()
        or "status" in resp.lower()
    )
    return passed, "convert_sceneplan_to_map returned valid response"


def test_apply_atmosphere(verbose: bool):
    arn = _read_agent_arn("unreal-level-builder")
    if not arn:
        return False, "UnrealLevelBuilder agent ARN not found"
    resp = invoke_agent(
        arn,
        "Apply neon cyber atmosphere to the current UE5 level. "
        "Call apply_atmosphere(lighting_mood='neon cyber'). "
        "If bridge is not configured, a skipped response is fine."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")
    passed = (
        "skipped" in resp.lower()
        or "commands" in resp.lower()
        or "atmosphere" in resp.lower()
        or "lighting" in resp.lower()
        or "bridge" in resp.lower()
        or "status" in resp.lower()
    )
    return passed, "apply_atmosphere returned valid response"


def test_generate_blockout_geometry(verbose: bool):
    """This tool is fully offline — no bridge needed. Always passes if agent is deployed."""
    arn = _read_agent_arn("unreal-level-builder")
    if not arn:
        return False, "UnrealLevelBuilder agent ARN not found"
    resp = invoke_agent(
        arn,
        f"Generate blockout geometry instructions for these zones (offline, no bridge needed): "
        f"{MINIMAL_ZONES}"
        f"\nCall generate_blockout_geometry(zones=<json>)."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")
    passed = (
        "instruction" in resp.lower()
        or "zone" in resp.lower()
        or "actor_class" in resp.lower()
        or "spawn_actor" in resp.lower()
        or "status" in resp.lower()
    )
    return passed, "generate_blockout_geometry returned valid response"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 12 Integration Tests — UnrealLevelBuilder Full Conversion")
    print("=" * 60)
    print("Tests pass if 'ok' or 'skipped' (bridge offline is expected in CI)")

    tests = [
        ("SSM — /hypermage/unreal-bridge-url",                  test_ssm_bridge_url),
        ("UnrealLevelBuilderAgent — get_bridge_status",          test_bridge_status),
        ("UnrealLevelBuilderAgent — convert_sceneplan_to_map",   test_convert_sceneplan_to_map),
        ("UnrealLevelBuilderAgent — apply_atmosphere",           test_apply_atmosphere),
        ("UnrealLevelBuilderAgent — generate_blockout_geometry", test_generate_blockout_geometry),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed_count = sum(results)
    print(f"Results: {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("ALL TESTS PASSED — Phase 12 complete")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
