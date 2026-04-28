"""
Phase 20 Integration Test
==========================
Validates the interactive object system end-to-end.

Tests:
  1. World-state API — POST state → 200 ok
  2. World-state API — GET state back → round-trip matches
  3. World-state API — GET unknown object → 404
  4. World-state API — POST missing fields → 400
  5. DynamoDB — item written by POST exists in hypermage-vr-world-state-dev
  6. SSM — /hypermage/world-state/api-url populated with live endpoint
  7. Source — HMVRInteractableComponent.WorldStateApiUrl is a settable static (not const)
  8. Source — HMVRGameMode::InitGame sets WorldStateApiUrl
  9. Source — WebPlatformAgent has persistObjState + loadObjectStates + WORLD_STATE_URL
"""

import json
import sys
import uuid
from pathlib import Path

import boto3
import urllib.request
import urllib.error

REGION       = "eu-west-1"
PROJECT_NAME = "hypermage-vr"
ENVIRONMENT  = "dev"

WORLD_STATE_TABLE = f"{PROJECT_NAME}-world-state-{ENVIRONMENT}"
WORLD_STATE_SSM   = "/hypermage/world-state/api-url"

REPO_ROOT      = Path(__file__).parent.parent
SOURCE_DIR     = REPO_ROOT / "UnrealProject" / "Source" / "HyperMageVR"
WEB_AGENT_SRC  = REPO_ROOT / "Agents" / "web-platform" / "src" / "main.py"


def run_test(name, fn, verbose):
    print(f"\n[TEST] {name}")
    try:
        passed, info = fn(verbose)
        print(f"  {'PASS' if passed else 'FAIL'} — {info}")
        return passed
    except Exception as exc:
        print(f"  ERROR — {exc}")
        return False


def _get_api_url(verbose):
    ssm = boto3.client("ssm", region_name=REGION)
    url = ssm.get_parameter(Name=WORLD_STATE_SSM)["Parameter"]["Value"]
    if verbose:
        print(f"  API URL: {url}")
    return url.rstrip("/")


def _http(method, url, body=None):
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ── API tests ─────────────────────────────────────────────────────────────────

def test_post_state(verbose):
    """POST /world-state with valid body → 200 {ok: true}."""
    base = _get_api_url(verbose)
    obj_id = f"phase20-test-{uuid.uuid4().hex[:8]}"
    status, body = _http("POST", f"{base}/world-state", {"object_id": obj_id, "state": "Active"})
    if verbose:
        print(f"  object_id={obj_id}  status={status}  body={body}")
    ok = status == 200 and body.get("ok") is True
    # stash for next test
    test_post_state._obj_id = obj_id
    return ok, f"POST /world-state → HTTP {status}, ok={body.get('ok')}"

test_post_state._obj_id = None


def test_get_state_roundtrip(verbose):
    """GET /world-state/{object_id} returns the state just written."""
    base   = _get_api_url(verbose)
    obj_id = test_post_state._obj_id
    if not obj_id:
        return False, "Skipped — test_post_state did not run first"
    status, body = _http("GET", f"{base}/world-state/{obj_id}")
    if verbose:
        print(f"  status={status}  body={body}")
    ok = status == 200 and body.get("state") == "Active"
    return ok, f"GET /world-state/{obj_id} → state={body.get('state')!r} (expected 'Active')"


def test_get_not_found(verbose):
    """GET /world-state/{unknown} → 404."""
    base   = _get_api_url(verbose)
    obj_id = f"does-not-exist-{uuid.uuid4().hex}"
    status, body = _http("GET", f"{base}/world-state/{obj_id}")
    if verbose:
        print(f"  status={status}  body={body}")
    ok = status == 404 and "error" in body
    return ok, f"GET unknown object → HTTP {status}"


def test_post_missing_fields(verbose):
    """POST /world-state with missing state → 400."""
    base = _get_api_url(verbose)
    status, body = _http("POST", f"{base}/world-state", {"object_id": "incomplete"})
    if verbose:
        print(f"  status={status}  body={body}")
    ok = status == 400 and "error" in body
    return ok, f"POST missing state → HTTP {status}"


def test_dynamodb_item_written(verbose):
    """DynamoDB table contains the item written by test_post_state."""
    obj_id = test_post_state._obj_id
    if not obj_id:
        return False, "Skipped — test_post_state did not run first"
    ddb   = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(WORLD_STATE_TABLE)
    resp  = table.get_item(Key={"object_id": obj_id})
    item  = resp.get("Item")
    if verbose:
        print(f"  DynamoDB item: {item}")
    ok = item is not None and item.get("state") == "Active"
    # cleanup
    try:
        table.delete_item(Key={"object_id": obj_id})
    except Exception:
        pass
    return ok, f"DynamoDB item found — state={item.get('state') if item else 'MISSING'!r}"


def test_ssm_url_set(verbose):
    """SSM /hypermage/world-state/api-url is populated."""
    ssm = boto3.client("ssm", region_name=REGION)
    val = ssm.get_parameter(Name=WORLD_STATE_SSM)["Parameter"]["Value"]
    if verbose:
        print(f"  SSM value: {val}")
    ok = val.startswith("https://") and "execute-api" in val
    return ok, f"SSM → {val}"


# ── Source code checks ────────────────────────────────────────────────────────

def test_component_settable_static(verbose):
    """HMVRInteractableComponent.h: WorldStateApiUrl is a non-const static."""
    header = SOURCE_DIR / "HMVRInteractableComponent.h"
    content = header.read_text(encoding="utf-8")
    has_static     = "static FString WorldStateApiUrl" in content
    has_no_const   = "static const FString WorldStateApiUrl" not in content
    if verbose:
        print(f"  static FString present: {has_static}")
        print(f"  const removed: {has_no_const}")
    ok = has_static and has_no_const
    return ok, "WorldStateApiUrl is a settable static (const removed)"


def test_gamemodesets_url(verbose):
    """HMVRGameMode.cpp sets WorldStateApiUrl in InitGame."""
    cpp = SOURCE_DIR / "HMVRGameMode.cpp"
    content = cpp.read_text(encoding="utf-8")
    checks = {
        "include InteractableComponent": "HMVRInteractableComponent.h" in content,
        "sets WorldStateApiUrl":         "WorldStateApiUrl" in content,
        "no TODO placeholder":           "TODO: set after terraform apply" not in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "HMVRGameMode sets WorldStateApiUrl" if ok else f"Issues: {missing}"


def test_browser_world_state(verbose):
    """WebPlatformAgent has persistObjState, loadObjectStates, and WORLD_STATE_URL injection."""
    content = WEB_AGENT_SRC.read_text(encoding="utf-8")
    checks = {
        "WORLD_STATE_URL_SSM constant": "WORLD_STATE_URL_SSM" in content,
        "WORLD_STATE_URL injected":     "WORLD_STATE_URL" in content,
        "persistObjState function":     "persistObjState" in content,
        "loadObjectStates function":    "loadObjectStates" in content,
        "persistent flag in JS array":  'persistent:' in content,
        "SSM read in generate_web_scene": "_get_ssm(WORLD_STATE_URL_SSM)" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "Browser world-state integration complete" if ok else f"Missing: {missing}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 20 Integration Tests — Interactive Object System + World-State Persistence")
    print("=" * 75)

    tests = [
        ("API     — POST /world-state valid body → 200 ok",                   test_post_state),
        ("API     — GET /world-state/{id} round-trip state matches",          test_get_state_roundtrip),
        ("API     — GET /world-state/{unknown} → 404",                        test_get_not_found),
        ("API     — POST /world-state missing field → 400",                   test_post_missing_fields),
        ("DynamoDB — item written by POST exists in world-state table",       test_dynamodb_item_written),
        ("SSM     — /hypermage/world-state/api-url populated",                test_ssm_url_set),
        ("Source  — WorldStateApiUrl is settable static (const removed)",     test_component_settable_static),
        ("Source  — HMVRGameMode::InitGame sets WorldStateApiUrl",            test_gamemodesets_url),
        ("Source  — WebPlatformAgent has persist/load + WORLD_STATE_URL",     test_browser_world_state),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 75)
    passed = sum(results)
    print(f"Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("ALL TESTS PASSED — Phase 20 world-state persistence complete")
        print()
        print("Remaining Phase 20 items (require home PC):")
        print("  - BehaviorTree asset (UE Editor)")
        print("  - APK rebuild with C++ world-state changes")
        return 0

    failed_names = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed_names:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
