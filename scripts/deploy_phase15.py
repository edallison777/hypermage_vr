"""
Deploy Phase 15: Server Rebuild & Fleet Update
===============================================
Steps:
  1. terraform apply — Phase 14 IAM only (execute-api:Invoke policy for fleet role)
  2. scripts/phase15/01-rebuild-server.sh — EC2 SSM build with Phase 13/14 C++ changes
  3. scripts/phase15/02-deploy-fleet.sh — create-build + fleet replace + FlexMatch update

C++ changes compiled in this phase:
  - HMVRPlayerState.h/.cpp       — Cognito PlayerId replication via PlayerState
  - HMVRGameMode.cpp             — Login() decodes JWT sub → PlayerId
  - AwsSigV4.h/.cpp              — SigV4 HTTP signing (OpenSSL HMAC-SHA256)
  - SessionAPIClient.h/.cpp      — real POST /session-summary + /interaction-events
  - HyperMageVR.Build.cs         — HTTP + OpenSSL dependencies
  - HMVRGameInstance.cpp         — real matchmaking HTTP (Phase 13)

Usage:
    GITHUB_TOKEN=ghp_xxx PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase15.py

    # Skip the EC2 rebuild (HyperMageVRServer.zip already current in S3):
    SKIP_REBUILD=1 PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase15.py

    # Skip Step 1 IAM (already applied — e.g. after a partial run):
    SKIP_IAM=1 GITHUB_TOKEN=ghp_xxx PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase15.py

    # Skip both IAM and rebuild (fleet destroyed, zip current, just re-register + deploy):
    SKIP_IAM=1 SKIP_REBUILD=1 PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase15.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT    = Path(__file__).parent.parent
TF_DIR       = REPO_ROOT / "Infra" / "environments" / "dev"
PHASE15_DIR  = REPO_ROOT / "scripts" / "phase15"
BUILD_ID_FILE = REPO_ROOT / ".phase15-build-id"

SKIP_IAM     = os.environ.get("SKIP_IAM",     "0") == "1"
SKIP_REBUILD = os.environ.get("SKIP_REBUILD", "0") == "1"


def run(cmd: list[str], cwd: Path) -> int:
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


def _find_git_bash() -> str:
    """Return the path to Git Bash's bash.exe, avoiding WSL."""
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    # Last resort — whatever is on PATH (may be WSL, but user can fix)
    import shutil
    return shutil.which("bash") or "bash"


def run_bash(script: Path, cwd: Path) -> int:
    bash_exe = _find_git_bash()
    # Convert Windows backslash path to forward-slash for bash
    script_posix = str(script).replace("\\", "/")
    print(f"\n$ {bash_exe} {script_posix}")
    result = subprocess.run([bash_exe, script_posix], cwd=str(cwd), env=os.environ.copy())
    return result.returncode


def _get_current_build_id() -> str:
    """Return the build ID currently in Terraform state, or 'placeholder' if not found."""
    # Prefer the saved file from a previous Phase 15 run
    if BUILD_ID_FILE.exists():
        bid = BUILD_ID_FILE.read_text().strip()
        if bid:
            return bid

    # Try to read from Terraform state
    try:
        result = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=str(TF_DIR), capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            state = json.loads(result.stdout)
            resources = (
                state.get("values", {})
                     .get("root_module", {})
                     .get("child_modules", [])
            )
            for mod in resources:
                if "gamelift_fleet" in mod.get("address", ""):
                    for r in mod.get("resources", []):
                        if r.get("type") == "aws_gamelift_fleet":
                            bid = r.get("values", {}).get("build_id", "")
                            if bid:
                                return bid
    except Exception:
        pass

    return "placeholder"


def step_terraform_phase14_iam() -> int:
    """
    Apply ONLY the Phase 14 IAM policy on the GameLift fleet role.
    Uses -target to avoid touching the fleet resource itself.
    """
    if SKIP_IAM:
        print("\n" + "=" * 60)
        print("STEP 1: SKIPPED (SKIP_IAM=1) — IAM policy already applied")
        print("=" * 60)
        return 0

    print("\n" + "=" * 60)
    print("STEP 1: Terraform — Phase 14 IAM (session-api-invoke policy only)")
    print("=" * 60)

    rc = run(["terraform", "init", "-upgrade"], TF_DIR)
    if rc != 0:
        print("FAILED: terraform init")
        return rc

    build_id = _get_current_build_id()
    print(f"Using build_id for plan context: {build_id}")

    # -target restricts the plan to ONLY the IAM policy resource.
    # This prevents Terraform from touching aws_gamelift_fleet even if build_id drifts.
    rc = run([
        "terraform", "apply",
        "-target=module.gamelift_fleet.aws_iam_role_policy.fleet_session_api",
        "-target=module.gamelift_fleet.aws_iam_role.fleet",
        "-target=module.gamelift_fleet.aws_iam_role_policy.fleet_logs",
        "-target=module.gamelift_fleet.aws_iam_role_policy.fleet_s3",
        f"-var=gamelift_build_id={build_id}",
        "-auto-approve",
    ], TF_DIR)
    if rc != 0:
        print("FAILED: terraform apply (IAM targets)")
        return rc

    print("\nTerraform Phase 14 IAM: OK")
    return 0


def step_rebuild_server() -> int:
    """Rebuild UE5 Linux dedicated server with Phase 13/14 C++ changes."""
    if SKIP_REBUILD:
        print("\n" + "=" * 60)
        print("STEP 2: SKIPPED (SKIP_REBUILD=1) — using existing HyperMageVRServer.zip")
        print("=" * 60)
        return 0

    print("\n" + "=" * 60)
    print("STEP 2: Rebuild UE5 Linux Server (30-90 minutes)")
    print("=" * 60)

    rc = run_bash(PHASE15_DIR / "01-rebuild-server.sh", REPO_ROOT)
    if rc != 0:
        print("FAILED: 01-rebuild-server.sh")
        return rc

    print("\nServer rebuild: OK")
    return 0


def step_deploy_fleet() -> int:
    """Create new GameLift build and deploy fleet."""
    print("\n" + "=" * 60)
    print("STEP 3: Deploy new GameLift fleet (30-45 min fleet activate)")
    print("=" * 60)

    rc = run_bash(PHASE15_DIR / "02-deploy-fleet.sh", REPO_ROOT)
    if rc != 0:
        print("FAILED: 02-deploy-fleet.sh")
        return rc

    print("\nFleet deployment: OK")
    return 0


def main():
    print("Phase 15 Deployment — Server Rebuild & Fleet Update")
    print("=" * 60)
    flags = []
    if SKIP_IAM:     flags.append("SKIP_IAM=1")
    if SKIP_REBUILD: flags.append("SKIP_REBUILD=1")
    if flags:
        print(f"NOTE: {', '.join(flags)}")
    print()

    steps = [
        ("Terraform Phase 14 IAM",   step_terraform_phase14_iam),
        ("Rebuild UE5 Linux Server",  step_rebuild_server),
        ("Deploy GameLift Fleet",    step_deploy_fleet),
    ]

    for name, fn in steps:
        rc = fn()
        if rc != 0:
            print(f"\nFAILED at step: {name}")
            sys.exit(rc)

    print("\n" + "=" * 60)
    print("ALL STEPS COMPLETE — Phase 15 deployed")
    print()
    print("Post-deploy checklist:")
    fleet_id = ""
    try:
        r = subprocess.run(
            ["terraform", "output", "-raw", "gamelift_fleet_id"],
            cwd=str(TF_DIR), capture_output=True, text=True
        )
        fleet_id = r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        pass
    fid = fleet_id or "<fleet_id from terraform output gamelift_fleet_id>"
    print(f"  1. Scale fleet up:")
    print(f"     aws gamelift update-fleet-capacity --fleet-id {fid} --desired-instances 1 --region eu-west-1")
    print()
    print("  2. Validate:")
    print("     PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase15.py")
    print()
    print("  3. Live E2E: Quest 3 login → matchmaking → connect → leave → DynamoDB with real PlayerId")
    print("     aws dynamodb scan --table-name hypermage-vr-player-sessions-dev --region eu-west-1")
    print()
    print(f"  4. Scale fleet back down:")
    print(f"     aws gamelift update-fleet-capacity --fleet-id {fid} --desired-instances 0 --region eu-west-1")


if __name__ == "__main__":
    main()
