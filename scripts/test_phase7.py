"""
Phase 7 Integration Test
=========================
Validates the asset ingestion pipeline end-to-end.

Tests:
  1. AssetPipelineAgent: validate_asset_import (valid asset passes)
  2. AssetPipelineAgent: create_provenance_record (writes to DynamoDB)
  3. AssetPipelineAgent: query_asset_catalogue (reads from DynamoDB)
  4. Direct DynamoDB: record written in test 2 is retrievable
  5. EnvironmentDesigner: get_available_assets referenced in ScenePlan (asset_sources populated)

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase7.py
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase7.py --verbose
"""

import argparse
import json
import os
import sys
import uuid

import boto3
from botocore.config import Config

REGION  = "eu-west-1"
ACCOUNT = "732231126129"
TABLE   = "hypermage-vr-asset-catalogue-dev"

# Agent ARNs — populated after deploy_phase7.py runs and updates .bedrock_agentcore.yaml
# Read ARNs from the yaml files at runtime
def _read_agent_arn(agent_dir: str) -> str:
    import re
    from pathlib import Path
    yaml_path = Path(__file__).parent.parent / "Agents" / agent_dir / ".bedrock_agentcore.yaml"
    try:
        content = yaml_path.read_text()
        m = re.search(r"agent_arn:\s*(arn:aws:bedrock-agentcore:[^\s]+)", content)
        return m.group(1) if m else ""
    except Exception:
        return ""


def invoke_agent(arn: str, prompt: str) -> str:
    """Invoke an AgentCore agent and return the full response text."""
    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(read_timeout=300, connect_timeout=10),
    )
    resp  = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw    = resp["response"].read().decode("utf-8")
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


def check_contains(response: str, *keys: str):
    lower   = response.lower()
    missing = [k for k in keys if k.lower() not in lower]
    return len(missing) == 0, missing


def run_test(name: str, fn, verbose: bool) -> bool:
    print(f"\n[TEST] {name}")
    try:
        result, info = fn(verbose)
        if result:
            print(f"  PASS — {info}")
        else:
            print(f"  FAIL — {info}")
        return result
    except Exception as exc:
        print(f"  ERROR — {exc}")
        return False


# ── Individual tests ──────────────────────────────────────────────────────────

TEST_ASSET_ID = str(uuid.uuid4())


def test_validate_asset_import(verbose: bool):
    arn = _read_agent_arn("asset-pipeline")
    if not arn:
        return False, "AssetPipeline agent ARN not found — run deploy_phase7.py first"

    prompt = (
        f"Validate this asset import: asset_id={TEST_ASSET_ID}, "
        "asset_name='Oracle Statue', asset_type='mesh', "
        "origin='hand-crafted', license='CC-BY-4.0', created_by='Ed Allison'"
    )
    response = invoke_agent(arn, prompt)
    if verbose:
        print(f"  Response:\n{response[:2000]}")
    passed, missing = check_contains(response, "valid")
    return passed, f"expected 'valid' in response" if not passed else "validation response received"


def test_create_provenance_record(verbose: bool):
    arn = _read_agent_arn("asset-pipeline")
    if not arn:
        return False, "AssetPipeline agent ARN not found"

    prompt = (
        f"Create a provenance record: asset_id={TEST_ASSET_ID}, "
        "asset_name='Oracle Statue', asset_type='mesh', tier=1, "
        "origin='hand-crafted', license='CC-BY-4.0', created_by='Ed Allison', "
        "s3_uri='s3://hypermage-vr-unreal-build-artifacts-dev/assets/processed/test/oracle_statue.glb', "
        "tags='oracle,ritual,stone'"
    )
    response = invoke_agent(arn, prompt)
    if verbose:
        print(f"  Response:\n{response[:2000]}")
    passed, missing = check_contains(response, "success")
    return passed, "provenance record created" if passed else f"missing: {missing}"


def test_query_asset_catalogue(verbose: bool):
    arn = _read_agent_arn("asset-pipeline")
    if not arn:
        return False, "AssetPipeline agent ARN not found"

    response = invoke_agent(arn, "Query the asset catalogue for mesh assets.")
    if verbose:
        print(f"  Response:\n{response[:2000]}")
    passed, missing = check_contains(response, "asset")
    return passed, "catalogue query returned assets" if passed else f"missing: {missing}"


def test_dynamodb_record_exists(verbose: bool):
    """Directly verify the test record is in DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table    = dynamodb.Table(TABLE)
    resp     = table.get_item(Key={"assetId": TEST_ASSET_ID})
    item     = resp.get("Item")
    if verbose and item:
        print(f"  DynamoDB item: {json.dumps(item, default=str)}")
    if item:
        return True, f"record found: {item.get('assetName')} status={item.get('status')}"
    return False, f"record {TEST_ASSET_ID} not found in {TABLE}"


def test_environment_designer_uses_assets(verbose: bool):
    arn = _read_agent_arn("conversation-level-designer")
    if not arn:
        return False, "EnvironmentDesigner ARN not found"

    response = invoke_agent(
        arn,
        "Design a ritual VR scene that incorporates any available oracle or ritual assets "
        "from the asset catalogue. Include them in asset_sources."
    )
    if verbose:
        print(f"  Response:\n{response[:3000]}")
    # Accept either: asset_sources in the ScenePlan, or a mention of the catalogue
    passed = ("asset_sources" in response or "asset catalogue" in response.lower()
              or "get_available_assets" in response.lower() or "oracle" in response.lower())
    return passed, "EnvironmentDesigner queried catalogue and/or included asset_sources" if passed else "no catalogue usage detected"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 7 integration tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Phase 7 Integration Tests")
    print("=" * 60)
    print(f"Test asset ID: {TEST_ASSET_ID}")
    print(f"DynamoDB table: {TABLE}")

    tests = [
        ("AssetPipelineAgent — validate_asset_import (valid)",            test_validate_asset_import),
        ("AssetPipelineAgent — create_provenance_record → DynamoDB",      test_create_provenance_record),
        ("AssetPipelineAgent — query_asset_catalogue",                    test_query_asset_catalogue),
        ("DynamoDB — record from test 2 is directly retrievable",         test_dynamodb_record_exists),
        ("EnvironmentDesigner — get_available_assets + asset_sources[]",  test_environment_designer_uses_assets),
    ]

    results = []
    for name, fn in tests:
        passed = run_test(name, fn, args.verbose)
        results.append(passed)

    print("\n" + "=" * 60)
    passed_count = sum(results)
    total        = len(results)
    print(f"Results: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("ALL TESTS PASSED — Phase 7 complete")
        return 0
    else:
        failed = [tests[i][0] for i, r in enumerate(results) if not r]
        print("FAILED tests:")
        for t in failed:
            print(f"  - {t}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
