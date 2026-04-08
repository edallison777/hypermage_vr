"""
Deploy Phase 14: Session Persistence & Real PlayerId
=====================================================
Steps:
  1. terraform apply — adds execute-api:Invoke policy to GameLift fleet role
     (new variable: session_api_execution_arn → grants POST /session-summary)
  2. No agent redeploy needed — all changes are C++ (compiled in Phase 15)

C++ changes in this phase (compiled as part of Phase 15 server rebuild):
  - HMVRPlayerState.h/.cpp       — PlayerState carrying Cognito PlayerId
  - HMVRGameMode.cpp             — Login() populates PlayerId; OnPlayerJoined/Left reads it
  - AwsSigV4.h/.cpp              — minimal SigV4 signer (OpenSSL HMAC-SHA256)
  - SessionAPIClient.h/.cpp      — real HTTP POST to /session-summary + /interaction-events
  - HyperMageVR.Build.cs         — OpenSSL third-party dependency added

Terraform changes:
  - gamelift-fleet/main.tf       — fleet_session_api policy (execute-api:Invoke)
  - gamelift-fleet/variables.tf  — session_api_execution_arn variable
  - session-api/outputs.tf       — api_execution_arn output
  - environments/dev/main.tf     — wires execution ARN to fleet module

Usage:
    PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/deploy_phase14.py
"""

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TF_DIR = Path(__file__).parent.parent / "Infra" / "environments" / "dev"


def run(cmd: list[str], cwd: Path) -> int:
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


def main():
    print("Phase 14 Deployment — Session Persistence & Real PlayerId")
    print("=" * 60)
    print("Terraform: adding execute-api:Invoke policy to GameLift fleet role")
    print()

    # terraform init (picks up new module output)
    rc = run(["terraform", "init", "-upgrade"], TF_DIR)
    if rc != 0:
        print("FAILED: terraform init")
        sys.exit(rc)

    # terraform plan
    rc = run(["terraform", "plan", "-out=phase14.tfplan"], TF_DIR)
    if rc != 0:
        print("FAILED: terraform plan")
        sys.exit(rc)

    # terraform apply
    rc = run(["terraform", "apply", "-auto-approve", "phase14.tfplan"], TF_DIR)
    if rc != 0:
        print("FAILED: terraform apply")
        sys.exit(rc)

    print("\n" + "=" * 60)
    print("ALL STEPS COMPLETE — Phase 14 Terraform done")
    print()
    print("IAM: GameLift fleet role can now call POST /session-summary")
    print()
    print("C++ changes are ready for Phase 15 server rebuild.")
    print("Next steps:")
    print("  1. Run test_phase14.py to validate the API is callable:")
    print("     PYTHONIOENCODING=utf-8 /c/Python312/python.exe scripts/test_phase14.py")
    print("  2. Proceed to Phase 15: UE5 Linux server rebuild + GameLift fleet update")


if __name__ == "__main__":
    main()
