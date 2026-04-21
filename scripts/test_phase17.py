"""
Phase 17 Integration Test
==========================
Validates live E2E on Quest 3 with Phase 16 error-UX Blueprint.

Tests:
  1. GameLift fleet is ACTIVE with Phase 15 build
  2. GameLift alias points to the current fleet
  3. C++ source: HMVRStatusWidget has all 5 BlueprintImplementableEvent handlers
  4. C++ source: HMVRGameInstance has all 4 BlueprintAssignable delegates + StatusWidgetClass
  5. C++ source: MainMenuLevelName is declared (ReturnToMainMenu is wired)
  6. (--check-e2e) DynamoDB player-sessions has real Cognito sub (no GUIDs) after live run
  7. (--check-e2e) Fleet capacity is back at 0 after testing

Tests 1-5 are always run; tests 6-7 require --check-e2e (run after live Quest 3 session).

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase17.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase17.py --verbose
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase17.py --check-e2e
"""

import argparse
import json
import re
import sys
from pathlib import Path

import boto3
from botocore.config import Config

REGION       = "eu-west-1"
PROJECT_NAME = "hypermage-vr"
ENVIRONMENT  = "dev"
FLEET_ID     = "fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9"
ALIAS_ID     = "alias-e67abbec-14ba-4e6d-8e95-6b0edfaad18e"
SESSIONS_TABLE = f"{PROJECT_NAME}-player-sessions-{ENVIRONMENT}"

REPO_ROOT  = Path(__file__).parent.parent
SOURCE_DIR = REPO_ROOT / "UnrealProject" / "Source" / "HyperMageVR"


def run_test(name, fn, verbose):
    print(f"\n[TEST] {name}")
    try:
        passed, info = fn(verbose)
        print(f"  {'PASS' if passed else 'FAIL'} — {info}")
        return passed
    except Exception as exc:
        print(f"  ERROR — {exc}")
        return False


# ── AWS tests ─────────────────────────────────────────────────────────────────

def test_fleet_active(verbose):
    """Fleet fleet-bdae1b71 is ACTIVE with Phase 15 build."""
    gl = boto3.client("gamelift", region_name=REGION, config=Config(read_timeout=30))
    resp = gl.describe_fleet_attributes(FleetIds=[FLEET_ID])
    fleets = resp.get("FleetAttributes", [])
    if not fleets:
        return False, f"Fleet {FLEET_ID} not found"
    fleet = fleets[0]
    status = fleet["Status"]
    build_id = fleet.get("BuildId", "unknown")
    if verbose:
        print(f"  Fleet: {FLEET_ID}  status={status}  build={build_id}")
    ok = status == "ACTIVE"
    return ok, f"Fleet {status} (build: {build_id})"


def test_alias_points_to_fleet(verbose):
    """GameLift alias points to the current Phase 15 fleet."""
    gl = boto3.client("gamelift", region_name=REGION, config=Config(read_timeout=30))
    resp = gl.describe_alias(AliasId=ALIAS_ID)
    alias = resp.get("Alias", {})
    routing = alias.get("RoutingStrategy", {})
    target_fleet = routing.get("FleetId", "")
    if verbose:
        print(f"  Alias {ALIAS_ID} → {target_fleet}")
    ok = target_fleet == FLEET_ID
    return ok, (
        f"Alias → {target_fleet} (correct)" if ok
        else f"Alias points to wrong fleet: {target_fleet} (expected {FLEET_ID})"
    )


# ── Source code checks ─────────────────────────────────────────────────────────

def test_status_widget_complete(verbose):
    """HMVRStatusWidget has all 5 BlueprintImplementableEvent handlers."""
    widget_h = SOURCE_DIR / "HMVRStatusWidget.h"
    if not widget_h.exists():
        return False, "HMVRStatusWidget.h not found"

    content = widget_h.read_text(encoding="utf-8")
    checks = {
        "UUserWidget base":            "UUserWidget" in content,
        "ShowSearching":               "ShowSearching" in content,
        "ShowConnecting":              "ShowConnecting" in content,
        "ShowError":                   "ShowError" in content,
        "ShowSuccess":                 "ShowSuccess" in content,
        "HideWidget":                  "HideWidget" in content,
        "BlueprintNativeEvent": "BlueprintNativeEvent" in content,
        "OnRetryRequested":            "OnRetryRequested" in content,
        "OnCancelRequested":           "OnCancelRequested" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {'ok' if v else 'MISSING'}")
    missing = [k for k, v in checks.items() if not v]
    ok = len(missing) == 0
    return ok, "HMVRStatusWidget complete" if ok else f"Missing: {missing}"


def test_game_instance_delegates(verbose):
    """HMVRGameInstance has 4 BlueprintAssignable delegates + StatusWidgetClass."""
    gi_h = SOURCE_DIR / "HMVRGameInstance.h"
    if not gi_h.exists():
        return False, "HMVRGameInstance.h not found"

    content = gi_h.read_text(encoding="utf-8")
    checks = {
        "OnMatchmakingStatusChanged": "OnMatchmakingStatusChanged" in content,
        "OnMatchmakingError":         "OnMatchmakingError" in content,
        "OnConnectionEstablished":    "OnConnectionEstablished" in content,
        "OnConnectionError":          "OnConnectionError" in content,
        "StatusWidgetClass":          "StatusWidgetClass" in content,
        "BlueprintAssignable":        "BlueprintAssignable" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {'ok' if v else 'MISSING'}")
    missing = [k for k, v in checks.items() if not v]
    ok = len(missing) == 0
    return ok, "HMVRGameInstance delegates complete" if ok else f"Missing: {missing}"


def test_main_menu_level_name(verbose):
    """MainMenuLevelName is declared and ReturnToMainMenu is implemented."""
    gi_h   = SOURCE_DIR / "HMVRGameInstance.h"
    gi_cpp = SOURCE_DIR / "HMVRGameInstance.cpp"
    if not gi_h.exists() or not gi_cpp.exists():
        return False, "HMVRGameInstance source not found"

    h_content   = gi_h.read_text(encoding="utf-8")
    cpp_content = gi_cpp.read_text(encoding="utf-8")
    checks = {
        "MainMenuLevelName declared": "MainMenuLevelName" in h_content,
        "ReturnToMainMenu declared":  "ReturnToMainMenu" in h_content,
        "ReturnToMainMenu impl":      "ReturnToMainMenu" in cpp_content,
        "OpenLevel call":             "OpenLevel" in cpp_content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {'ok' if v else 'MISSING'}")
    missing = [k for k, v in checks.items() if not v]
    ok = len(missing) == 0
    return ok, "ReturnToMainMenu wired" if ok else f"Missing: {missing}"


def test_auto_login_implemented(verbose):
    """Persistent refresh token: HMVRSaveGame exists, auto-login flow wired in GameInstance."""
    save_h  = SOURCE_DIR / "HMVRSaveGame.h"
    gi_h    = SOURCE_DIR / "HMVRGameInstance.h"
    gi_cpp  = SOURCE_DIR / "HMVRGameInstance.cpp"

    checks = {
        "HMVRSaveGame.h exists":       save_h.exists(),
        "RefreshToken field":          save_h.exists() and "RefreshToken" in save_h.read_text(encoding="utf-8"),
        "SetRefreshToken declared":    "SetRefreshToken" in gi_h.read_text(encoding="utf-8"),
        "OnAutoLoginComplete delegate":"OnAutoLoginComplete" in gi_h.read_text(encoding="utf-8"),
        "TryAutoLogin impl":           "TryAutoLogin" in gi_cpp.read_text(encoding="utf-8"),
        "REFRESH_TOKEN_AUTH":          "REFRESH_TOKEN_AUTH" in gi_cpp.read_text(encoding="utf-8"),
        "ClearSavedCredentials impl":  "ClearSavedCredentials" in gi_cpp.read_text(encoding="utf-8"),
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {'ok' if v else 'MISSING'}")
    missing = [k for k, v in checks.items() if not v]
    ok = len(missing) == 0
    return ok, "Auto-login flow complete" if ok else f"Missing: {missing}"


# ── E2E checks (post live-test) ────────────────────────────────────────────────

def test_no_guid_playerids_in_dynamo(verbose):
    """
    DynamoDB player-sessions contains only real Cognito subs — no random GUIDs.
    Run after a live Quest 3 session has completed.
    """
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(SESSIONS_TABLE)
    guid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    resp = table.scan(ProjectionExpression="playerId", Limit=100)
    items = resp.get("Items", [])

    if verbose:
        for item in items[:10]:
            print(f"  playerId: {item['playerId']}")

    guids = [
        i["playerId"] for i in items
        if guid_pattern.match(i.get("playerId", ""))
        and "phase1" not in i.get("playerId", "")
    ]
    if guids:
        return False, f"{len(guids)} GUID playerIds found (old stub): {guids[:3]}"
    if not items:
        return True, "No session records yet — complete a live Quest 3 session first"
    return True, f"{len(items)} session records — all use real Cognito sub (no GUIDs)"


def test_fleet_scaled_down(verbose):
    """Fleet desired capacity is back at 0 after testing (cost control)."""
    gl = boto3.client("gamelift", region_name=REGION, config=Config(read_timeout=30))
    resp = gl.describe_fleet_capacity(FleetIds=[FLEET_ID])
    capacities = resp.get("FleetCapacity", [])
    if not capacities:
        return False, f"Could not read capacity for {FLEET_ID}"
    cap = capacities[0].get("InstanceCounts", {})
    desired = cap.get("DESIRED", -1)
    active  = cap.get("ACTIVE", -1)
    if verbose:
        print(f"  DESIRED={desired}  ACTIVE={active}")
    ok = desired == 0
    return ok, (
        f"Fleet scaled down (DESIRED=0, ACTIVE={active})" if ok
        else f"Fleet still at DESIRED={desired} — run scale-down command"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--check-e2e", action="store_true",
        help="Also check DynamoDB for GUID playerIds and fleet scale-down (run after live Quest 3 session)")
    args = parser.parse_args()

    print("Phase 17 Integration Tests — Live E2E on Quest 3 + Error UX Blueprint")
    print("=" * 70)

    tests = [
        ("GameLift — fleet ACTIVE with Phase 15 build",                test_fleet_active),
        ("GameLift — alias points to current fleet",                    test_alias_points_to_fleet),
        ("Source — HMVRStatusWidget has all 5 event handlers",          test_status_widget_complete),
        ("Source — HMVRGameInstance delegates + StatusWidgetClass",     test_game_instance_delegates),
        ("Source — MainMenuLevelName declared + ReturnToMainMenu impl",  test_main_menu_level_name),
        ("Source — Auto-login: SaveGame + refresh token flow wired",    test_auto_login_implemented),
    ]

    if args.check_e2e:
        tests += [
            ("DynamoDB — no GUID playerIds (real Cognito subs only)",  test_no_guid_playerids_in_dynamo),
            ("GameLift — fleet scaled back to 0 (cost control)",       test_fleet_scaled_down),
        ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 70)
    passed = sum(results)
    print(f"Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("ALL TESTS PASSED — Phase 17 complete")
        print()
        if args.check_e2e:
            print("Phase 17 fully validated — ready for Phase 18: Interaction Systems + Voice + QA")
        else:
            print("Pre-live checks OK. Complete the Blueprint setup and live Quest 3 test,")
            print("then run:  python scripts/test_phase17.py --check-e2e")
        return 0

    failed_names = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed_names:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
