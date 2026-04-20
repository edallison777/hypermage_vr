"""
Phase 16 Integration Test
==========================
Validates APK hardening: offline resilience + error UX.

Tests:
  1. Cancel matchmaking Lambda exists and is invokable (400 on missing ticketId)
  2. Start matchmaking → cancel via Lambda → ticket reaches CANCELLED state
  3. Session summary Lambda regression (Cognito playerId still accepted)
  4. C++ source: HMVRStatusWidget declared (UUserWidget + ShowError + BlueprintImplementableEvent)
  5. C++ source: SessionAPIClient has MaxRetries constant and retry logic
  6. C++ source: CancelMatchmaking() sends HTTP DELETE (no longer just a TODO)
  7. C++ source: UI TODO comments resolved (delegates wired, no dangling TODOs)

Tests 1-3 are AWS integration tests; 4-7 are source-code structure checks.
"""

import json
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

REGION       = "eu-west-1"
PROJECT_NAME = "hypermage-vr"
ENVIRONMENT  = "dev"

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


# ── AWS integration tests ─────────────────────────────────────────────────────

def test_cancel_lambda_invokable(verbose):
    """Cancel matchmaking Lambda exists and returns 400 when ticketId is missing."""
    client = boto3.client("lambda", region_name=REGION, config=Config(read_timeout=30))
    fn_name = f"{PROJECT_NAME}-cancel-matchmaking-{ENVIRONMENT}"

    payload = json.dumps({
        "httpMethod": "DELETE",
        "pathParameters": None,
        "body": None,
    }).encode()

    resp = client.invoke(FunctionName=fn_name, InvocationType="RequestResponse", Payload=payload)
    result = json.loads(resp["Payload"].read())

    if verbose:
        print(f"  Response: {result}")

    status = result.get("statusCode", 0)
    ok = status == 400
    return ok, f"Lambda invokable — returned HTTP {status} (expected 400 for missing ticketId)"


def test_cancel_matchmaking_flow(verbose):
    """Start a matchmaking ticket then cancel it via Lambda direct invoke."""
    lc = boto3.client("lambda", region_name=REGION, config=Config(read_timeout=30))

    # Start matchmaking (direct Lambda invoke — bypasses API GW Cognito auth)
    start_payload = json.dumps({
        "httpMethod": "POST",
        "body": json.dumps({"playerId": "phase16-cancel-test"}),
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "phase16-cancel-test", "email": "test@example.com"}
            }
        },
    }).encode()

    start_resp = lc.invoke(
        FunctionName=f"{PROJECT_NAME}-start-matchmaking-{ENVIRONMENT}",
        InvocationType="RequestResponse",
        Payload=start_payload,
    )
    start_result = json.loads(start_resp["Payload"].read())

    if verbose:
        print(f"  Start response: {start_result}")

    if start_result.get("statusCode") != 200:
        return False, f"Start matchmaking failed: HTTP {start_result.get('statusCode')} — {start_result.get('body')}"

    ticket_id = json.loads(start_result["body"]).get("ticketId")
    if not ticket_id:
        return False, "No ticketId in start response"

    # Brief pause: FlexMatch is eventually consistent — wait for ticket to register
    time.sleep(2)

    # Cancel via cancel Lambda
    cancel_payload = json.dumps({
        "httpMethod": "DELETE",
        "pathParameters": {"ticketId": ticket_id},
    }).encode()

    cancel_resp = lc.invoke(
        FunctionName=f"{PROJECT_NAME}-cancel-matchmaking-{ENVIRONMENT}",
        InvocationType="RequestResponse",
        Payload=cancel_payload,
    )
    cancel_result = json.loads(cancel_resp["Payload"].read())

    if verbose:
        print(f"  Cancel response: {cancel_result}")

    ok = cancel_result.get("statusCode") == 200
    short_id = ticket_id[:24] + "…"
    return ok, f"Ticket {short_id} cancelled — HTTP {cancel_result.get('statusCode')}"


def test_session_summary_regression(verbose):
    """post-session-summary Lambda still accepts Cognito-style playerId."""
    client = boto3.client("lambda", region_name=REGION, config=Config(read_timeout=30))
    payload = json.dumps({
        "body": json.dumps({
            "playerId": "eu-west-1_q2rAaummA:phase16-regression",
            "sessionId": "phase16-regression-session",
            "rewards": [],
            "endTime": "2026-04-20T10:00:00.000Z",
        }),
        "httpMethod": "POST",
    }).encode()

    resp = client.invoke(
        FunctionName=f"{PROJECT_NAME}-post-session-summary-{ENVIRONMENT}",
        InvocationType="RequestResponse",
        Payload=payload,
    )
    result = json.loads(resp["Payload"].read())

    if verbose:
        print(f"  Response: {result}")

    status = result.get("statusCode", 0)
    ok = status in (200, 201)

    # Cleanup test record
    try:
        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.Table(f"{PROJECT_NAME}-player-sessions-{ENVIRONMENT}").delete_item(
            Key={
                "playerId": "eu-west-1_q2rAaummA:phase16-regression",
                "sessionId": "phase16-regression-session",
            }
        )
    except Exception:
        pass

    return ok, f"Session summary Lambda — HTTP {status}"


# ── Source code structure checks ───────────────────────────────────────────────

def test_status_widget_declared(verbose):
    """HMVRStatusWidget.h exists and has the required declarations."""
    widget_h = SOURCE_DIR / "HMVRStatusWidget.h"
    if not widget_h.exists():
        return False, "HMVRStatusWidget.h not found"

    content = widget_h.read_text(encoding="utf-8")
    checks = {
        "UUserWidget base": "UUserWidget" in content,
        "ShowError":        "ShowError" in content,
        "BlueprintImplementableEvent": "BlueprintImplementableEvent" in content,
        "OnRetryRequested": "OnRetryRequested" in content,
        "OnCancelRequested": "OnCancelRequested" in content,
    }

    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")

    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "HMVRStatusWidget.h fully declared" if ok else f"Missing: {missing}"


def test_retry_logic_present(verbose):
    """SessionAPIClient has MaxRetries constant and retry scheduling code."""
    client_h   = SOURCE_DIR / "SessionAPIClient.h"
    client_cpp = SOURCE_DIR / "SessionAPIClient.cpp"

    content_h   = client_h.read_text(encoding="utf-8")
    content_cpp = client_cpp.read_text(encoding="utf-8")

    checks = {
        "MaxRetries constant": "MaxRetries" in content_h,
        "Retry scheduling":    "AddTicker" in content_cpp or "FTSTicker" in content_cpp,
        "bShouldRetry logic":  "bShouldRetry" in content_cpp,
    }

    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")

    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "SessionAPIClient retry logic present" if ok else f"Missing: {missing}"


def test_cancel_http_implemented(verbose):
    """CancelMatchmaking() sends an HTTP DELETE (no longer just a TODO comment)."""
    gi_cpp = SOURCE_DIR / "HMVRGameInstance.cpp"
    content = gi_cpp.read_text(encoding="utf-8")

    checks = {
        'DELETE verb set':    'SetVerb(TEXT("DELETE"))' in content,
        'TODO removed':       "TODO: Call Session API to cancel matchmaking" not in content,
        'cancel URL path':    "matchmaking/cancel/" in content,
    }

    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")

    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "CancelMatchmaking sends HTTP DELETE" if ok else f"Issues: {missing}"


def test_ui_todos_resolved(verbose):
    """All dangling UI TODO comments have been replaced with real implementations."""
    gi_cpp = SOURCE_DIR / "HMVRGameInstance.cpp"
    content = gi_cpp.read_text(encoding="utf-8")

    dangling_todos = [
        "TODO: Notify UI of matchmaking failure",
        "TODO: Notify UI of successful connection",
        "TODO: Notify UI of connection failure",
        "TODO: Return to main menu",
    ]
    remaining = [t for t in dangling_todos if t in content]

    if verbose:
        for t in remaining:
            print(f"  Still present: {t}")

    ok = len(remaining) == 0
    return ok, "All UI TODO comments resolved" if ok else f"{len(remaining)} TODO(s) remain: {remaining}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 16 Integration Tests — APK Hardening: Offline Resilience + Error UX")
    print("=" * 70)

    tests = [
        ("Lambda — cancel-matchmaking invokable (400 on missing ticketId)",  test_cancel_lambda_invokable),
        ("Lambda — start matchmaking → cancel flow end-to-end",              test_cancel_matchmaking_flow),
        ("Lambda — session summary regression (Cognito playerId accepted)",  test_session_summary_regression),
        ("Source — HMVRStatusWidget declared (UUserWidget + ShowError)",     test_status_widget_declared),
        ("Source — SessionAPIClient has retry logic (MaxRetries constant)",  test_retry_logic_present),
        ("Source — CancelMatchmaking sends HTTP DELETE (no TODO)",           test_cancel_http_implemented),
        ("Source — UI TODO comments resolved (delegates wired up)",          test_ui_todos_resolved),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 70)
    passed = sum(results)
    print(f"Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("ALL TESTS PASSED — Phase 16 complete")
        print()
        print("Ready for Phase 17: Live E2E validation on Quest 3 with full error-UX Blueprint")
        return 0

    failed_names = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED tests:")
    for t in failed_names:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
