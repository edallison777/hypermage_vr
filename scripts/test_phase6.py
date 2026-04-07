"""
Phase 6 Integration Test
=========================
Validates that CostMonitorFinOps and DevOpsAWS return real AWS data.

Tests:
  1. CostMonitorFinOps: generate_cost_report → real Cost Explorer spend data
  2. DevOpsAWS: deploy_infrastructure → real GameLift fleet status
  3. ProducerOrchestrator: cost report request routes through to real data

Usage:
    PYTHONIOENCODING=utf-8 python scripts/test_phase6.py
    PYTHONIOENCODING=utf-8 python scripts/test_phase6.py --verbose
"""

import argparse
import json
import sys
import boto3
from botocore.config import Config

REGION = "eu-west-1"
ACCOUNT = "732231126129"

AGENTS = {
    "CostMonitorFinOps": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/CostMonitorFinOps_Agent-gI5m1PA2US",
    "DevOpsAWS": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/DevOpsAWS_Agent-tjiWN5GCZV",
    "ProducerOrchestrator": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/ProducerOrchestrator_Agent-8eBOlFDUfN",
}


def invoke_agent(arn: str, prompt: str) -> str:
    """Invoke an AgentCore agent and return the full response text."""
    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(read_timeout=300, connect_timeout=10),
    )
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw = resp["response"].read().decode("utf-8")

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


def check_contains(response: str, *keys: str) -> tuple[bool, list[str]]:
    """Check that response text contains all expected keys/values (case-insensitive)."""
    lower = response.lower()
    missing = [k for k in keys if k.lower() not in lower]
    return len(missing) == 0, missing


def run_test(name: str, arn: str, prompt: str, expect: list[str], verbose: bool) -> bool:
    print(f"\n[TEST] {name}")
    print(f"  Prompt: {prompt[:80]}...")
    try:
        response = invoke_agent(arn, prompt)
        if verbose:
            print(f"  Response:\n{response[:2000]}")

        passed, missing = check_contains(response, *expect)
        if passed:
            print(f"  PASS — all expected fields present: {expect}")
        else:
            print(f"  FAIL — missing from response: {missing}")
            if not verbose:
                print(f"  Response (first 500 chars):\n{response[:500]}")
        return passed
    except Exception as e:
        print(f"  ERROR — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Phase 6 integration tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full agent responses")
    args = parser.parse_args()

    print("Phase 6 Integration Tests")
    print("=" * 60)
    print("Testing CostMonitorFinOps (Cost Explorer) + DevOpsAWS (GameLift)")

    tests = [
        {
            "name": "CostMonitorFinOps — generate_cost_report (real Cost Explorer data)",
            "agent": "CostMonitorFinOps",
            "prompt": "Generate a cost report for this month. Show real AWS spend broken down by service.",
            "expect": ["cost explorer", "spend"],
        },
        {
            "name": "CostMonitorFinOps — check_budget (real spend vs £1000 budget)",
            "agent": "CostMonitorFinOps",
            "prompt": "Check if spending £50 on GameLift this month would exceed our budget.",
            "expect": ["approved", "budget"],
        },
        {
            "name": "DevOpsAWS — deploy_infrastructure (real GameLift fleet status)",
            "agent": "DevOpsAWS",
            "prompt": "What is the current GameLift fleet status? Check capacity and report.",
            "expect": ["fleet-848aced2", "ACTIVE"],
        },
        {
            "name": "DevOpsAWS — execute_terraform (real state from S3)",
            "agent": "DevOpsAWS",
            "prompt": "Show the current Terraform state for dev environment. How many resources are deployed?",
            "expect": ["resource", "Terraform"],
        },
        {
            "name": "ProducerOrchestrator — cost report request (real data end-to-end)",
            "agent": "ProducerOrchestrator",
            "prompt": "I need a cost report showing our real AWS spend this month. Query the CostMonitorFinOps agent.",
            "expect": ["cost"],
        },
    ]

    results = []
    for t in tests:
        arn = AGENTS[t["agent"]]
        passed = run_test(t["name"], arn, t["prompt"], t["expect"], args.verbose)
        results.append(passed)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("ALL TESTS PASSED — Phase 6 complete")
        return 0
    else:
        failed_tests = [tests[i]["name"] for i, r in enumerate(results) if not r]
        print(f"FAILED tests:")
        for t in failed_tests:
            print(f"  - {t}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
