"""
G6 Integration Test
====================
Validates Cognito + matchmaking integration in the Godot VR client.

Tests (always run — source + infra checks):
  1. aws_cognito.gd exists with correct CLIENT_ID and ENDPOINT
  2. matchmaking_client.gd exists with correct API_BASE
  3. game_network.gd exists with sv_welcome @rpc
  4. vr_main.gd reads AutoLogin.txt and wires all signals
  5. main_vr.tscn has StatusLabel, CognitoAuth, MatchmakingClient, GameNetwork nodes
  6. export_presets.cfg has internet permission enabled
  7. Cognito: live auth test with credentials from AutoLogin.txt
  8. Matchmaking: start + poll with live Cognito token (starts real ECS task)

Usage:
    python scripts/test_g6.py
    python scripts/test_g6.py --verbose
    python scripts/test_g6.py --skip-live   # skip tests 7-8 (source checks only)
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3

REGION = "eu-west-1"
COGNITO_CLIENT_ID = "2iinqhoja78kj1et6rcv28bjvf"
COGNITO_ENDPOINT  = "https://cognito-idp.eu-west-1.amazonaws.com/"
SESSION_API_BASE  = "https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"

REPO_ROOT   = Path(__file__).parent.parent
GODOT_DIR   = REPO_ROOT / "GodotProject"
SCRIPTS_DIR = GODOT_DIR / "scripts"
SCENES_DIR  = GODOT_DIR / "scenes"

AUTO_LOGIN  = REPO_ROOT / "AutoLogin.txt"

LAMBDA_START  = "hypermage-vr-start-matchmaking-dev"
LAMBDA_STATUS = "hypermage-vr-get-matchmaking-status-dev"


def run_test(name, fn, verbose):
    print(f"\n[TEST] {name}")
    try:
        passed, info = fn(verbose)
        print(f"  {'PASS' if passed else 'FAIL'} -- {info}")
        return passed
    except Exception as exc:
        print(f"  ERROR -- {exc}")
        return False


# ── Source checks ─────────────────────────────────────────────────────────────

def test_cognito_script(verbose):
    f = SCRIPTS_DIR / "aws_cognito.gd"
    if not f.exists():
        return False, "aws_cognito.gd not found"
    content = f.read_text(encoding="utf-8")
    checks = {
        "CLIENT_ID present": COGNITO_CLIENT_ID in content,
        "ENDPOINT present":  "cognito-idp.eu-west-1.amazonaws.com" in content,
        "auth_success signal": "signal auth_success" in content,
        "auth_failed signal":  "signal auth_failed" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "aws_cognito.gd ok" if ok else f"Missing: {missing}"


def test_matchmaking_script(verbose):
    f = SCRIPTS_DIR / "matchmaking_client.gd"
    if not f.exists():
        return False, "matchmaking_client.gd not found"
    content = f.read_text(encoding="utf-8")
    checks = {
        "API_BASE present":          "fhjoxyk9x5.execute-api.eu-west-1" in content,
        "matchmaking_complete signal": "signal matchmaking_complete" in content,
        "TIMEOUT constant":           "TIMEOUT_SECS" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "matchmaking_client.gd ok" if ok else f"Missing: {missing}"


def test_game_network_script(verbose):
    f = SCRIPTS_DIR / "game_network.gd"
    if not f.exists():
        return False, "game_network.gd not found"
    content = f.read_text(encoding="utf-8")
    checks = {
        "ENetMultiplayerPeer":    "ENetMultiplayerPeer" in content,
        "connected_to_server":    "signal connected_to_server" in content,
        "sv_welcome @rpc":        "@rpc" in content and "sv_welcome" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "game_network.gd ok" if ok else f"Missing: {missing}"


def test_vr_main_script(verbose):
    f = SCRIPTS_DIR / "vr_main.gd"
    if not f.exists():
        return False, "vr_main.gd not found"
    content = f.read_text(encoding="utf-8")
    checks = {
        "reads AutoLogin.txt":      "AutoLogin.txt" in content,
        "cognito.login call":       "cognito.login" in content,
        "matchmaking.start call":   "matchmaking.start" in content,
        "connect_to_server call":   "connect_to_server" in content,
        "status label set":         "_set_status" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "vr_main.gd ok" if ok else f"Missing: {missing}"


def test_main_vr_tscn(verbose):
    f = SCENES_DIR / "main_vr.tscn"
    if not f.exists():
        return False, "main_vr.tscn not found"
    content = f.read_text(encoding="utf-8")
    checks = {
        "StatusLabel node":     '"StatusLabel"' in content,
        "CognitoAuth node":     '"CognitoAuth"' in content,
        "MatchmakingClient node": '"MatchmakingClient"' in content,
        "GameNetwork node":     '"GameNetwork"' in content,
        "aws_cognito script":   "aws_cognito.gd" in content,
        "matchmaking script":   "matchmaking_client.gd" in content,
        "game_network script":  "game_network.gd" in content,
    }
    if verbose:
        for k, v in checks.items():
            print(f"  {k}: {v}")
    ok = all(checks.values())
    missing = [k for k, v in checks.items() if not v]
    return ok, "main_vr.tscn has all G6 nodes" if ok else f"Missing: {missing}"


def test_internet_permission(verbose):
    f = GODOT_DIR / "export_presets.cfg"
    content = f.read_text(encoding="utf-8")
    ok = "permissions/internet=true" in content
    if verbose:
        print(f"  internet permission: {'enabled' if ok else 'DISABLED'}")
    return ok, "export_presets.cfg: internet=true" if ok else "internet permission NOT enabled -- HTTP will fail on device"


# ── Live tests ────────────────────────────────────────────────────────────────

def _read_autologin():
    if not AUTO_LOGIN.exists():
        raise RuntimeError(f"AutoLogin.txt not found at {AUTO_LOGIN}")
    lines = AUTO_LOGIN.read_text(encoding="utf-8").splitlines()
    return lines[0].strip(), lines[1].strip()


def _cognito_auth(username, password):
    body = json.dumps({
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": COGNITO_CLIENT_ID,
        "AuthParameters": {"USERNAME": username, "PASSWORD": password}
    }).encode()
    req = urllib.request.Request(COGNITO_ENDPOINT, data=body, headers={
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def test_live_cognito(verbose):
    username, password = _read_autologin()
    if verbose:
        print(f"  logging in as {username}...")
    resp = _cognito_auth(username, password)
    id_token = resp.get("AuthenticationResult", {}).get("IdToken", "")
    ok = bool(id_token)
    test_live_cognito._id_token = id_token
    return ok, f"Cognito auth ok, token length={len(id_token)}"

test_live_cognito._id_token = ""


def _invoke_lambda(fn, payload):
    lm = boto3.client("lambda", region_name=REGION)
    resp = lm.invoke(FunctionName=fn, Payload=json.dumps(payload).encode())
    raw = json.loads(resp["Payload"].read())
    body = json.loads(raw.get("body", "{}"))
    return raw.get("statusCode", 0), body


def test_live_matchmaking(verbose):
    id_token = test_live_cognito._id_token
    if not id_token:
        return False, "Skipped -- live_cognito did not run first"

    import base64
    parts = id_token.split(".")
    payload_b64 = parts[1] + "=="
    payload = json.loads(base64.b64decode(payload_b64))
    player_id = payload.get("sub", "test-player-g6")
    if verbose:
        print(f"  player_id from JWT: {player_id}")

    code, body = _invoke_lambda(LAMBDA_START, {
        "body": json.dumps({"playerId": player_id}),
        "requestContext": {"authorizer": {"claims": {"sub": player_id}}}
    })
    if code != 200:
        return False, f"start-matchmaking returned HTTP {code}: {body}"

    ticket_id = body.get("ticketId", "")
    if not ticket_id:
        return False, "No ticketId in response"
    if verbose:
        print(f"  ticketId: {ticket_id}")

    print("  Polling for COMPLETED (up to 90s)...")
    for attempt in range(18):
        time.sleep(5)
        code, body = _invoke_lambda(LAMBDA_STATUS, {
            "pathParameters": {"ticketId": ticket_id},
            "requestContext": {}
        })
        status = body.get("status", "UNKNOWN")
        if verbose:
            print(f"    [{attempt+1}/18] {status}")
        else:
            print(f"    [{attempt+1}/18] {status}", end="\r", flush=True)
        if status == "COMPLETED":
            conn = body.get("gameSessionConnectionInfo", {})
            ip = conn.get("ipAddress", "")
            port = conn.get("port", 7777)
            print()
            return True, f"COMPLETED -- server at {ip}:{port}"
        if status == "FAILED":
            print()
            return False, f"FAILED: {body.get('statusReason', 'unknown')}"

    print()
    return False, "Timed out after 90s"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--skip-live", action="store_true", help="Skip Cognito + matchmaking live tests")
    args = parser.parse_args()

    print("G6 Integration Tests -- Cognito + Matchmaking from Godot VR client")
    print("=" * 65)

    tests = [
        ("Source -- aws_cognito.gd has CLIENT_ID + signals",         test_cognito_script),
        ("Source -- matchmaking_client.gd has API_BASE + signals",    test_matchmaking_script),
        ("Source -- game_network.gd has ENet + sv_welcome @rpc",      test_game_network_script),
        ("Source -- vr_main.gd reads AutoLogin.txt + wires signals",  test_vr_main_script),
        ("Scene  -- main_vr.tscn has all G6 nodes",                   test_main_vr_tscn),
        ("Config -- export_presets.cfg internet=true",                 test_internet_permission),
    ]

    if not args.skip_live:
        tests += [
            ("Live   -- Cognito auth with AutoLogin.txt credentials",   test_live_cognito),
            ("Live   -- matchmaking start + poll returns server IP",     test_live_matchmaking),
        ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 65)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("ALL TESTS PASSED -- G6 Godot VR client integration complete")
        print()
        print("Next: build APK and test on Quest 3")
        print("  python GodotProject/tools/build_vr_room.py --no-build --install")
        print("  -- OR rebuild with:")
        print("  C:\\Tools\\Godot\\Godot_v4.6.3-stable_win64_console.exe --headless --path GodotProject --export-debug Android GodotProject/export/HyperMageVR.apk")
        print()
        print("Push AutoLogin.txt to device:")
        print("  adb shell run-as com.hypermage.godot sh -c 'mkdir -p /data/data/com.hypermage.godot/files'")
        print("  adb shell run-as com.hypermage.godot sh -c 'cat > /data/data/com.hypermage.godot/files/AutoLogin.txt' < AutoLogin.txt")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
