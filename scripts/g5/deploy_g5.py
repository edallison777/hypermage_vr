"""
G5 Deploy Script
================
Deploys the Godot dedicated server infrastructure:
  1. npm install in Lambda directories (bundles ECS/EC2/DynamoDB SDK)
  2. terraform apply (creates ECR, ECS cluster, task def, SG, DynamoDB table)
  3. docker build + ECR push (Godot server image)
  4. Prints next steps for testing

Usage:
    cd <repo-root>
    python scripts/g5/deploy_g5.py [--skip-docker]

Flags:
    --skip-docker   Skip Docker build/push (useful if image already up-to-date)
    --skip-npm      Skip npm install (useful if node_modules already correct)
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys

ACCOUNT_ID = "732231126129"
REGION = "eu-west-1"

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
INFRA_DEV = REPO_ROOT / "Infra" / "environments" / "dev"
GODOT_DIR = REPO_ROOT / "GodotProject"

LAMBDA_DIRS = [
    REPO_ROOT / "Infra" / "modules" / "session-api" / "lambda" / "start-matchmaking",
    REPO_ROOT / "Infra" / "modules" / "session-api" / "lambda" / "get-matchmaking-status",
    REPO_ROOT / "Infra" / "modules" / "session-api" / "lambda" / "cancel-matchmaking",
]


def run(cmd, cwd=None, check=True, capture=False):
    print(f">>> {cmd}")
    kwargs = {"shell": True, "cwd": str(cwd) if cwd else None}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        print(f"ERROR: command exited {result.returncode}")
        sys.exit(result.returncode)
    return result


def step_npm_install():
    print("\n=== Step 1: npm install in Lambda directories ===")
    for d in LAMBDA_DIRS:
        print(f"\n  Installing in {d.name}...")
        run("npm install", cwd=d)


def step_terraform():
    print("\n=== Step 2: terraform apply ===")
    run("terraform init -upgrade", cwd=INFRA_DEV)
    run("terraform apply -auto-approve", cwd=INFRA_DEV)


def get_ecr_uri():
    result = run(
        "terraform output -json ecr_godot_server_uri",
        cwd=INFRA_DEV, capture=True
    )
    uri = json.loads(result.stdout.strip())
    return uri


def step_docker(ecr_uri):
    print(f"\n=== Step 3: docker build + push to {ecr_uri} ===")
    ecr_hostname = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com"

    # ECR login
    run(
        f"aws ecr get-login-password --region {REGION} | "
        f"docker login --username AWS --password-stdin {ecr_hostname}"
    )

    # Build
    run(f"docker build -t {ecr_uri}:latest .", cwd=GODOT_DIR)

    # Push
    run(f"docker push {ecr_uri}:latest")


def main():
    parser = argparse.ArgumentParser(description="G5 deploy: Godot server on ECS")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker build/push")
    parser.add_argument("--skip-npm", action="store_true", help="Skip npm install")
    args = parser.parse_args()

    print("G5 Deploy: Godot dedicated server on ECS Fargate")
    print("=" * 55)

    if not args.skip_npm:
        step_npm_install()
    else:
        print("\n[Skipped] npm install")

    step_terraform()
    ecr_uri = get_ecr_uri()
    print(f"\nECR URI: {ecr_uri}")

    if not args.skip_docker:
        step_docker(ecr_uri)
    else:
        print(f"\n[Skipped] Docker build/push — ensure {ecr_uri}:latest exists in ECR")

    print("\n" + "=" * 55)
    print("G5 deployment complete!")
    print()
    print("Next steps:")
    print("  1. Run integration test:")
    print("       python scripts/test_g5.py")
    print()
    print("  2. For a full E2E test (starts real ECS task, ~60s):")
    print("       python scripts/test_g5.py --e2e")
    print()
    print("  3. Check server logs in CloudWatch:")
    print(f"       /ecs/hypermage-vr-godot-server-dev")


if __name__ == "__main__":
    main()
