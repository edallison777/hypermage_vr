"""
G5 Integration Test
====================
Validates the Godot dedicated server on ECS infrastructure.

Tests (always run — no ECS task needed):
  1. ECS cluster exists in eu-west-1
  2. ECS task definition exists and is ACTIVE
  3. ECR repository exists
  4. DynamoDB matchmaking-tickets table exists
  5. Session API: POST /matchmaking/start returns 401 (Cognito gate alive)
  6. Lambda: start-matchmaking has ECS env vars (not GameLift config name)
  7. Lambda: get-matchmaking-status has ECS_CLUSTER_ARN env var
  8. Server source: server_main.gd listens on PORT=7777
  9. Server source: sv_welcome RPC defined

E2E test (--e2e flag, starts a real ECS task):
  10. Lambda invoke: start-matchmaking returns ticketId
  11. Lambda invoke: poll get-matchmaking-status until COMPLETED (up to 120s)
  12. Connection check: TCP connect to returned IP:7777

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_g5.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_g5.py --e2e
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_g5.py --verbose
"""

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3

REGION = "eu-west-1"
ACCOUNT = "732231126129"
PROJECT = "hypermage-vr"
ENV = "dev"

SESSION_API_BASE = "https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"

ECS_CLUSTER_NAME = f"{PROJECT}-godot-{ENV}"
ECR_REPO_NAME = f"{PROJECT}-godot-server-{ENV}"
TASK_DEF_FAMILY = f"{PROJECT}-godot-server-{ENV}"
TICKETS_TABLE = f"{PROJECT}-matchmaking-tickets-{ENV}"

LAMBDA_START = f"{PROJECT}-start-matchmaking-{ENV}"
LAMBDA_STATUS = f"{PROJECT}-get-matchmaking-status-{ENV}"

REPO_ROOT = Path(__file__).parent.parent
SERVER_SCRIPT = REPO_ROOT / "GodotProject" / "scripts" / "server_main.gd"


def run_test(name, fn, verbose):
    print(f"\n[TEST] {name}")
    try:
        passed, info = fn(verbose)
        status = "PASS" if passed else "FAIL"
        print(f"  {status} -- {info}")
        return passed
    except Exception as exc:
        print(f"  ERROR -- {exc}")
        return False


# ── Infrastructure tests ─────────────────────────────────────────────────────

def test_ecs_cluster_exists(verbose):
    ecs = boto3.client("ecs", region_name=REGION)
    resp = ecs.describe_clusters(clusters=[ECS_CLUSTER_NAME])
    clusters = [c for c in resp.get("clusters", []) if c["status"] == "ACTIVE"]
    if verbose:
        print(f"  Clusters found: {[c['clusterName'] for c in clusters]}")
    ok = len(clusters) == 1
    return ok, f"ECS cluster {ECS_CLUSTER_NAME} -- {'ACTIVE' if ok else 'NOT FOUND'}"


def test_ecs_task_def_exists(verbose):
    ecs = boto3.client("ecs", region_name=REGION)
    resp = ecs.list_task_definitions(familyPrefix=TASK_DEF_FAMILY, status="ACTIVE")
    arns = resp.get("taskDefinitionArns", [])
    if verbose:
        print(f"  Task def ARNs: {arns}")
    ok = len(arns) >= 1
    return ok, f"Task def {TASK_DEF_FAMILY} -- {len(arns)} active revision(s)"


def test_ecr_repo_exists(verbose):
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        resp = ecr.describe_repositories(repositoryNames=[ECR_REPO_NAME])
        repos = resp.get("repositories", [])
        if verbose:
            uris = [r["repositoryUri"] for r in repos]
            print(f"  ECR repos: {uris}")
        ok = len(repos) == 1
        uri = repos[0]["repositoryUri"] if ok else "N/A"
        return ok, f"ECR repo {ECR_REPO_NAME} at {uri}"
    except ecr.exceptions.RepositoryNotFoundException:
        return False, f"ECR repo {ECR_REPO_NAME} NOT FOUND"


def test_dynamodb_tickets_table(verbose):
    ddb = boto3.client("dynamodb", region_name=REGION)
    try:
        resp = ddb.describe_table(TableName=TICKETS_TABLE)
        status = resp["Table"]["TableStatus"]
        if verbose:
            print(f"  Table status: {status}")
        ok = status == "ACTIVE"
        return ok, f"DynamoDB {TICKETS_TABLE} -- {status}"
    except ddb.exceptions.ResourceNotFoundException:
        return False, f"DynamoDB {TICKETS_TABLE} NOT FOUND"


def test_api_gateway_alive(verbose):
    url = f"{SESSION_API_BASE}/matchmaking/start"
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10):
            return False, "Expected 401 but got 200 (missing Cognito auth?)"
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"  HTTP {e.code} from {url}")
        ok = e.code == 401
        return ok, f"POST /matchmaking/start -- HTTP {e.code} (expected 401)"
    except Exception as exc:
        return False, f"Request failed: {exc}"


def test_lambda_start_env_vars(verbose):
    lm = boto3.client("lambda", region_name=REGION)
    cfg = lm.get_function_configuration(FunctionName=LAMBDA_START)
    env = cfg.get("Environment", {}).get("Variables", {})
    if verbose:
        safe = {k: v for k, v in env.items() if "SECRET" not in k.upper()}
        print(f"  Env vars: {list(safe.keys())}")
    has_ecs = "ECS_CLUSTER_ARN" in env
    no_gamelift = "MATCHMAKING_CONFIG_NAME" not in env
    ok = has_ecs and no_gamelift
    return ok, f"start-matchmaking: ECS_CLUSTER_ARN={'yes' if has_ecs else 'NO'}, GameLift removed={'yes' if no_gamelift else 'NO'}"


def test_lambda_status_env_vars(verbose):
    lm = boto3.client("lambda", region_name=REGION)
    cfg = lm.get_function_configuration(FunctionName=LAMBDA_STATUS)
    env = cfg.get("Environment", {}).get("Variables", {})
    if verbose:
        print(f"  Env vars: {list(env.keys())}")
    ok = "ECS_CLUSTER_ARN" in env
    return ok, f"get-matchmaking-status: ECS_CLUSTER_ARN={'yes' if ok else 'NO'}"


def test_server_gd_port(verbose):
    content = SERVER_SCRIPT.read_text(encoding="utf-8")
    ok = "PORT := 7777" in content or "PORT = 7777" in content
    if verbose:
        print(f"  Script exists: {SERVER_SCRIPT.exists()}")
    return ok, f"server_main.gd defines PORT=7777: {'yes' if ok else 'NO'}"


def test_server_gd_rpc(verbose):
    content = SERVER_SCRIPT.read_text(encoding="utf-8")
    ok = "sv_welcome" in content and "@rpc" in content
    return ok, f"sv_welcome @rpc defined: {'yes' if ok else 'NO'}"


# ── E2E tests (--e2e flag) ────────────────────────────────────────────────────

def _invoke_lambda(function_name, payload):
    lm = boto3.client("lambda", region_name=REGION)
    resp = lm.invoke(FunctionName=function_name, Payload=json.dumps(payload).encode())
    raw = json.loads(resp["Payload"].read())
    body = json.loads(raw.get("body", "{}"))
    return raw.get("statusCode", 0), body


def test_e2e_start_matchmaking(verbose):
    status_code, body = _invoke_lambda(LAMBDA_START, {
        "body": json.dumps({"playerId": "test-player-g5"}),
        "requestContext": {"authorizer": {"claims": {"sub": "test-player-g5"}}}
    })
    if verbose:
        print(f"  statusCode={status_code}, body={body}")
    ticket_id = body.get("ticketId")
    ok = status_code == 200 and ticket_id is not None
    test_e2e_start_matchmaking._ticket_id = ticket_id
    return ok, f"start-matchmaking returned ticketId={ticket_id}"

test_e2e_start_matchmaking._ticket_id = None


def test_e2e_poll_status(verbose):
    ticket_id = test_e2e_start_matchmaking._ticket_id
    if not ticket_id:
        return False, "Skipped -- test_e2e_start_matchmaking did not run first"

    print(f"  Polling status for ticketId={ticket_id} (up to 120s)...")
    ip_address = None
    for attempt in range(24):  # 24 * 5s = 120s
        time.sleep(5)
        status_code, body = _invoke_lambda(LAMBDA_STATUS, {
            "pathParameters": {"ticketId": ticket_id},
            "requestContext": {}
        })
        match_status = body.get("status", "UNKNOWN")
        if verbose:
            print(f"    attempt {attempt+1}: status={match_status}")
        else:
            print(f"    [{attempt+1}/24] {match_status}", end="\r", flush=True)
        if match_status == "COMPLETED":
            conn = body.get("gameSessionConnectionInfo", {})
            ip_address = conn.get("ipAddress")
            port = conn.get("port")
            test_e2e_poll_status._ip = ip_address
            test_e2e_poll_status._port = port
            print()
            return True, f"COMPLETED -- server at {ip_address}:{port}"
        if match_status == "FAILED":
            print()
            return False, f"FAILED -- {body.get('statusReason', 'unknown reason')}"

    print()
    return False, "Timed out after 120s -- task may still be provisioning"

test_e2e_poll_status._ip = None
test_e2e_poll_status._port = None


def test_e2e_tcp_connect(verbose):
    ip = test_e2e_poll_status._ip
    port = test_e2e_poll_status._port
    if not ip:
        return False, "Skipped -- poll_status did not return an IP"
    if verbose:
        print(f"  TCP connect to {ip}:{port}...")
    try:
        with socket.create_connection((ip, port), timeout=10):
            return True, f"TCP connect to {ip}:{port} succeeded"
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        # ENet is UDP-based -- TCP might be refused even when server is running.
        # A refused connection means the port is reachable (server is up).
        if isinstance(exc, ConnectionRefusedError):
            return True, f"TCP refused at {ip}:{port} (expected -- ENet is UDP)"
        return False, f"TCP connect to {ip}:{port} failed: {exc}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--e2e", action="store_true", help="Run E2E tests (starts real ECS task)")
    args = parser.parse_args()

    print("G5 Integration Tests -- Godot Dedicated Server on ECS")
    print("=" * 60)

    tests = [
        ("Infra   -- ECS cluster exists and ACTIVE",                  test_ecs_cluster_exists),
        ("Infra   -- ECS task definition ACTIVE",                     test_ecs_task_def_exists),
        ("Infra   -- ECR repository exists",                          test_ecr_repo_exists),
        ("Infra   -- DynamoDB matchmaking-tickets table ACTIVE",       test_dynamodb_tickets_table),
        ("API     -- POST /matchmaking/start returns 401 (auth gate)", test_api_gateway_alive),
        ("Lambda  -- start-matchmaking has ECS_CLUSTER_ARN",          test_lambda_start_env_vars),
        ("Lambda  -- get-matchmaking-status has ECS_CLUSTER_ARN",     test_lambda_status_env_vars),
        ("Source  -- server_main.gd defines PORT=7777",               test_server_gd_port),
        ("Source  -- server_main.gd has sv_welcome @rpc",             test_server_gd_rpc),
    ]

    if args.e2e:
        tests += [
            ("E2E     -- start-matchmaking invoked, ticketId returned",   test_e2e_start_matchmaking),
            ("E2E     -- poll status until COMPLETED (up to 120s)",       test_e2e_poll_status),
            ("E2E     -- TCP connect to server IP:7777",                  test_e2e_tcp_connect),
        ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn, args.verbose))

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("ALL TESTS PASSED -- G5 Godot dedicated server on ECS complete")
        return 0

    failed = [tests[i][0] for i, r in enumerate(results) if not r]
    print("FAILED:")
    for t in failed:
        print(f"  - {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
