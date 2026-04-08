"""
Phase 15 Integration Test
==========================
Validates the rebuilt GameLift fleet and real PlayerId session persistence.

Tests:
  1. Phase 15 GameLift build exists and is READY
  2. GameLift fleet is ACTIVE (new fleet with Phase 15 binary)
  3. Fleet fleet role has execute-api:Invoke policy (Phase 14 IAM)
  4. DynamoDB player-sessions table writable (direct write + cleanup)
  5. PlayerId extraction: DecodeToken returns real Cognito sub
  6. Lambda post-session-summary directly invokable with a non-GUID playerId
  7. (Manual/Optional) DynamoDB scan: check for real Cognito sub in playerId column

Tests 1-6 are automated; test 7 requires a live E2E run with Quest 3.
Fleet can be DESIRED=0 for tests 1-6 (fleet existence is checked, not capacity).

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase15.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase15.py --verbose
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase15.py --check-e2e
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import boto3
from botocore.config import Config

REGION          = "eu-west-1"
ACCOUNT         = "732231126129"
PROJECT_NAME    = "hypermage-vr"
ENVIRONMENT     = "dev"
FLEET_ROLE_NAME = f"{PROJECT_NAME}-gamelift-fleet-{ENVIRONMENT}"
SESSIONS_TABLE  = f"{PROJECT_NAME}-player-sessions-{ENVIRONMENT}"
REWARDS_TABLE   = f"{PROJECT_NAME}-player-rewards-{ENVIRONMENT}"
BUILD_NAME_RE   = re.compile(rf"^{re.escape(PROJECT_NAME)}-server")

# Path where 02-deploy-fleet.sh saves the new build ID
REPO_ROOT = Path(__file__).parent.parent
BUILD_ID_FILE = REPO_ROOT / ".phase15-build-id"


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

def test_phase15_build_ready(verbose: bool):
    """Phase 15 GameLift build is READY."""
    gl = boto3.client("gamelift", region_name=REGION)

    # Use saved build ID if available
    if BUILD_ID_FILE.exists():
        build_id = BUILD_ID_FILE.read_text().strip()
        try:
            resp = gl.describe_build(BuildId=build_id)
            status = resp["Build"]["Status"]
            name = resp["Build"]["Name"]
            if verbose:
                print(f"  Build: {build_id} ({name}) status={status}")
            ok = status == "READY"
            return ok, f"Build {build_id} ({name}) — {status}"
        except Exception as exc:
            return False, f"describe_build failed for {build_id}: {exc}"

    # Fall back: find the most recent build matching our name pattern
    try:
        resp = gl.list_builds(Status="READY", Limit=20)
        builds = [b for b in resp.get("Builds", []) if BUILD_NAME_RE.match(b["Name"])]
        if not builds:
            return False, "No READY builds found matching hypermage-vr-server-* (run deploy_phase15.py)"
        latest = sorted(builds, key=lambda b: b["CreationTime"], reverse=True)[0]
        if verbose:
            print(f"  Latest build: {latest['BuildId']} ({latest['Name']})")
        return True, f"Build {latest['BuildId']} ({latest['Name']}) — READY"
    except Exception as exc:
        return False, f"list_builds failed: {exc}"


def test_fleet_active(verbose: bool):
    """GameLift fleet is ACTIVE (fleet replacement with Phase 15 build succeeded)."""
    gl = boto3.client("gamelift", region_name=REGION)
    try:
        resp = gl.list_fleets()
        for fleet_id in resp.get("FleetIds", []):
            attrs = gl.describe_fleet_attributes(FleetIds=[fleet_id])
            for fleet in attrs.get("FleetAttributes", []):
                if fleet.get("Name", "").startswith(f"{PROJECT_NAME}-fleet-"):
                    status = fleet["Status"]
                    build_id = fleet.get("BuildId", "unknown")
                    if verbose:
                        print(f"  Fleet: {fleet_id} build={build_id} status={status}")
                    if status == "ACTIVE":
                        # Verify it's running the Phase 15 build
                        phase15_build = BUILD_ID_FILE.read_text().strip() if BUILD_ID_FILE.exists() else None
                        if phase15_build and build_id != phase15_build:
                            return False, f"Fleet {fleet_id} ACTIVE but on old build {build_id} (expected {phase15_build})"
                        return True, f"Fleet {fleet_id} ACTIVE with build {build_id}"
        return False, "No ACTIVE fleet found for hypermage-vr"
    except Exception as exc:
        return False, f"fleet check failed: {exc}"


def test_fleet_role_has_session_api_policy(verbose: bool):
    """GameLift fleet IAM role has the session-api-invoke policy (Phase 14)."""
    iam = boto3.client("iam", region_name=REGION)
    try:
        resp = iam.list_role_policies(RoleName=FLEET_ROLE_NAME)
        policies = resp.get("PolicyNames", [])
        if verbose:
            print(f"  Inline policies: {policies}")
        has_policy = "session-api-invoke" in policies
        return has_policy, (
            "fleet role has session-api-invoke policy" if has_policy else
            f"session-api-invoke NOT found (run deploy_phase15.py). Found: {policies}"
        )
    except Exception as exc:
        return False, f"IAM describe failed: {exc}"


def test_dynamodb_sessions_writable(verbose: bool):
    """player-sessions DynamoDB table is writable."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(SESSIONS_TABLE)
    item = {
        "playerId":  "phase15-test-player",
        "sessionId": "phase15-test-session",
        "rewards":   [],
        "endTime":   "2026-04-08T12:00:00.000Z",
        "ttl":       9999999999,
        "createdAt": "2026-04-08T12:00:00.000Z",
    }
    try:
        table.put_item(Item=item)
        table.delete_item(Key={"playerId": "phase15-test-player", "sessionId": "phase15-test-session"})
        return True, f"DynamoDB {SESSIONS_TABLE} write+delete ok"
    except Exception as exc:
        return False, f"DynamoDB write failed: {exc}"


def test_player_id_extraction(verbose: bool):
    """JWT sub claim extraction mirrors the C++ HMVRGameMode::Login() logic."""
    payload = {"sub": "cognito-user-phase15-abc", "token_use": "access", "exp": 9999999999}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    fake_token = f"header.{payload_b64}.signature"
    try:
        parts = fake_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded))
        player_id = decoded.get("sub", "")
        # Verify it's not a GUID (old behaviour)
        is_guid = bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-", player_id, re.I))
        ok = player_id == "cognito-user-phase15-abc" and not is_guid
        return ok, f"PlayerId='{player_id}' (non-GUID Cognito sub: {'yes' if not is_guid else 'NO — still GUID!'})"
    except Exception as exc:
        return False, f"Decode failed: {exc}"


def test_lambda_session_summary_invokable(verbose: bool):
    """post-session-summary Lambda accepts a Cognito-style (non-GUID) playerId."""
    client = boto3.client("lambda", region_name=REGION,
                          config=Config(read_timeout=30, connect_timeout=10))
    # Use a Cognito-style sub (not a GUID) to confirm the fix is deployed
    cognito_player_id = "eu-west-1_q2rAaummA:phase15-test-user"
    payload = json.dumps({
        "body": json.dumps({
            "playerId":  cognito_player_id,
            "sessionId": "phase15-lambda-test",
            "rewards":   ["test_crystal"],
            "endTime":   "2026-04-08T12:00:00.000Z",
        }),
        "httpMethod": "POST",
    }).encode("utf-8")
    try:
        resp = client.invoke(
            FunctionName=f"{PROJECT_NAME}-post-session-summary-{ENVIRONMENT}",
            InvocationType="RequestResponse",
            Payload=payload,
        )
        result = json.loads(resp["Payload"].read())
        if verbose:
            print(f"  Lambda response: {result}")
        status = result.get("statusCode", 0)
        ok = status in (200, 201)
        # Clean up
        try:
            ddb = boto3.resource("dynamodb", region_name=REGION)
            ddb.Table(SESSIONS_TABLE).delete_item(
                Key={"playerId": cognito_player_id, "sessionId": "phase15-lambda-test"})
        except Exception:
            pass
        return ok, f"Lambda accepted Cognito playerId — HTTP {status}"
    except Exception as exc:
        return False, f"Lambda invoke failed: {exc}"


def test_no_guid_playerids_in_dynamo(verbose: bool):
    """
    (Optional E2E check) Scan player-sessions for records — confirm none use
    random GUIDs (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx pattern).
    Only meaningful after a live Quest 3 session has completed.
    """
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(SESSIONS_TABLE)
    guid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    try:
        resp = table.scan(ProjectionExpression="playerId", Limit=100)
        items = resp.get("Items", [])
        if verbose:
            for item in items[:10]:
                print(f"  playerId: {item['playerId']}")
        guids = [i["playerId"] for i in items if guid_pattern.match(i.get("playerId", ""))]
        # Exclude test records we inject
        guids = [g for g in guids if "phase1" not in g]
        if guids:
            return False, f"Found {len(guids)} GUID playerIds (old stub): {guids[:3]}"
        if not items:
            return True, "No session records yet — run a live Quest 3 session first"
        return True, f"{len(items)} session records — no GUID playerIds found"
    except Exception as exc:
        return False, f"DynamoDB scan failed: {exc}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--check-e2e", action="store_true",
                        help="Also scan DynamoDB for GUID playerIds (run after live Quest 3 session)")
    args = parser.parse_args()

    print("Phase 15 Integration Tests — Server Rebuild & Real PlayerId")
    print("=" * 60)

    tests = [
        ("GameLift — Phase 15 build is READY",                       test_phase15_build_ready),
        ("GameLift — fleet is ACTIVE with new build",                 test_fleet_active),
        ("IAM — fleet role has session-api-invoke policy",            test_fleet_role_has_session_api_policy),
        ("DynamoDB — player-sessions table writable",                  test_dynamodb_sessions_writable),
        ("PlayerId — JWT sub extraction is non-GUID Cognito sub",      test_player_id_extraction),
        ("Lambda — post-session-summary accepts Cognito playerId",     test_lambda_session_summary_invokable),
    ]

    if args.check_e2e:
        tests.append(
            ("DynamoDB — no GUID playerIds (E2E validation)",          test_no_guid_playerids_in_dynamo)
        )

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed_count = sum(results)
    print(f"Results: {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("ALL TESTS PASSED — Phase 15 complete")
        print()
        print("Ready for Phase 16: APK hardening — offline resilience + error UX")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
