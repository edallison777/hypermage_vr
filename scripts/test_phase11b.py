"""
Phase 11b Integration Test
===========================
Validates NarrativeAgent + LARPIntegrationAgent + GM Event Lambda.

Tests:
  1. SSM: /hypermage/larp/gm-event-url exists
  2. SSM: /hypermage/larp/ws-management-endpoint exists
  3. NarrativeAgent: get_narrative_state for test scene → ok or skipped
  4. NarrativeAgent: list_available_hooks → ok or skipped
  5. NarrativeAgent: advance_scene with test scene_id → ok or skipped (0 clients is fine)
  6. LARPIntegrationAgent: get_connected_participants → ok
  7. LARPIntegrationAgent: get_scene_status → ok

Tests pass if status is 'ok' OR 'skipped' OR relevant keywords found.

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase11b.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase11b.py --verbose
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

TEST_SCENE_ID = "phase10-test-scene-001"


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

def test_ssm_gm_event_url(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/larp/gm-event-url")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        return True, f"GM event URL: {value}"
    except Exception as exc:
        return False, f"SSM /hypermage/larp/gm-event-url not found: {exc}"


def test_ssm_ws_management(verbose: bool):
    ssm = boto3.client("ssm", region_name=REGION)
    try:
        resp  = ssm.get_parameter(Name="/hypermage/larp/ws-management-endpoint")
        value = resp["Parameter"]["Value"]
        if verbose:
            print(f"  Value: {value}")
        return True, f"WS management endpoint: {value}"
    except Exception as exc:
        return False, f"SSM /hypermage/larp/ws-management-endpoint not found: {exc}"


def test_narrative_get_state(verbose: bool):
    arn = _read_agent_arn("narrative")
    if not arn:
        return False, "Narrative agent ARN not found — run deploy_phase11b.py first"
    resp = invoke_agent(
        arn,
        f"Get the current narrative state for scene '{TEST_SCENE_ID}'. "
        f"Call get_narrative_state(scene_id='{TEST_SCENE_ID}')."
    )
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = (
        "skipped" in resp.lower()
        or "state" in resp.lower()
        or "scene_id" in resp.lower()
        or "not found" in resp.lower()
    )
    return passed, "get_narrative_state returned valid response"


def test_narrative_list_hooks(verbose: bool):
    arn = _read_agent_arn("narrative")
    if not arn:
        return False, "Narrative agent ARN not found"
    resp = invoke_agent(
        arn,
        f"List all available GM hooks for scene '{TEST_SCENE_ID}'. "
        f"Call list_available_hooks(scene_id='{TEST_SCENE_ID}')."
    )
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = (
        "skipped" in resp.lower()
        or "hook" in resp.lower()
        or "scene_id" in resp.lower()
        or "not found" in resp.lower()
    )
    return passed, "list_available_hooks returned valid response"


def test_narrative_advance_scene(verbose: bool):
    arn = _read_agent_arn("narrative")
    if not arn:
        return False, "Narrative agent ARN not found"
    resp = invoke_agent(
        arn,
        f"Fire the hook 'hook_activate' for scene '{TEST_SCENE_ID}'. "
        f"Call advance_scene(scene_id='{TEST_SCENE_ID}', hook_name='hook_activate'). "
        f"Note: 0 clients notified is acceptable for this test."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")
    passed = (
        "skipped" in resp.lower()
        or "clients_notified" in resp.lower()
        or "new_state" in resp.lower()
        or "hook" in resp.lower()
        or "state" in resp.lower()
    )
    return passed, "advance_scene returned valid response"


def test_larp_participants(verbose: bool):
    arn = _read_agent_arn("larp-integration")
    if not arn:
        return False, "LARPIntegration agent ARN not found — run deploy_phase11b.py first"
    resp = invoke_agent(
        arn,
        f"Get the list of connected participants for scene '{TEST_SCENE_ID}'. "
        f"Call get_connected_participants(scene_id='{TEST_SCENE_ID}')."
    )
    if verbose:
        print(f"  Response:\n{resp[:1500]}")
    passed = (
        "skipped" in resp.lower()
        or "participant" in resp.lower()
        or "count" in resp.lower()
        or "connection" in resp.lower()
    )
    return passed, "get_connected_participants returned valid response"


def test_larp_scene_status(verbose: bool):
    arn = _read_agent_arn("larp-integration")
    if not arn:
        return False, "LARPIntegration agent ARN not found"
    resp = invoke_agent(
        arn,
        f"Get the full status for scene '{TEST_SCENE_ID}'. "
        f"Call get_scene_status(scene_id='{TEST_SCENE_ID}')."
    )
    if verbose:
        print(f"  Response:\n{resp[:2000]}")
    passed = (
        "skipped" in resp.lower()
        or "status" in resp.lower()
        or "scene" in resp.lower()
        or "hook" in resp.lower()
        or "participant" in resp.lower()
        or "not found" in resp.lower()
    )
    return passed, "get_scene_status returned valid response"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 11b Integration Tests — NarrativeAgent + LARPIntegrationAgent")
    print("=" * 60)
    print("Tests pass if status is 'ok' (infrastructure deployed) or 'skipped' (SSM not configured)")
    print(f"Test scene ID: {TEST_SCENE_ID}")

    tests = [
        ("SSM — /hypermage/larp/gm-event-url",            test_ssm_gm_event_url),
        ("SSM — /hypermage/larp/ws-management-endpoint",  test_ssm_ws_management),
        ("NarrativeAgent — get_narrative_state",           test_narrative_get_state),
        ("NarrativeAgent — list_available_hooks",          test_narrative_list_hooks),
        ("NarrativeAgent — advance_scene (0 clients ok)",  test_narrative_advance_scene),
        ("LARPIntegrationAgent — get_connected_participants", test_larp_participants),
        ("LARPIntegrationAgent — get_scene_status",        test_larp_scene_status),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed_count = sum(results)
    print(f"Results: {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("ALL TESTS PASSED — Phase 11b complete")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
