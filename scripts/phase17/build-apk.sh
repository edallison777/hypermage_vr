#!/usr/bin/env bash
# build-apk.sh — Build the HyperMage VR Android APK (Quest 3) from the UE5 project
#               and optionally sideload it via ADB.
#
# This is a local Windows build — it calls RunUAT.bat using the UE5 install on this PC.
# No EC2 instance is involved (client-only changes: no server rebuild needed).
#
# Prerequisites:
#   - UE5.3 installed with Android platform support + Android SDK/NDK configured
#   - Quest 3 connected via ADB (wireless or USB) if using --install
#   - Run wireless-adb.bat first for wireless install
#
# Usage:
#   ./scripts/phase17/build-apk.sh              # build only
#   ./scripts/phase17/build-apk.sh --install    # build + sideload
#   ./scripts/phase17/build-apk.sh --install-only  # sideload existing APK without rebuilding
#
# Override UE5 install path:
#   UE5_ROOT="D:/Epic Games/UE_5.3" ./scripts/phase17/build-apk.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPROJECT="$REPO_ROOT/UnrealProject/HyperMageVR.uproject"
OUTPUT_DIR="$REPO_ROOT/Packaged/Android"
ADB="C:/Users/j_e_a/AppData/Local/Android/Sdk/platform-tools/adb.exe"

# ── Detect UE5 install ────────────────────────────────────────────────────────
UE5_ROOT="${UE5_ROOT:-}"
if [[ -z "$UE5_ROOT" ]]; then
  # Prefer newest installed version
  for candidate in \
    "C:/Program Files/Epic Games/UE_5.6" \
    "C:/Program Files/Epic Games/UE_5.5" \
    "C:/Program Files/Epic Games/UE_5.4" \
    "C:/Program Files/Epic Games/UE_5.3" \
    "D:/Epic Games/UE_5.6" \
    "D:/Epic Games/UE_5.5" \
    "D:/Epic Games/UE_5.4" \
    "D:/Epic Games/UE_5.3"; do
    if [[ -f "$candidate/Engine/Build/BatchFiles/RunUAT.bat" ]]; then
      UE5_ROOT="$candidate"
      break
    fi
  done
fi

if [[ -z "$UE5_ROOT" ]]; then
  echo "ERROR: Could not find UE5 install. Set UE5_ROOT env var:" >&2
  echo "  UE5_ROOT='D:/Epic Games/UE_5.3' ./scripts/phase17/build-apk.sh" >&2
  exit 1
fi

RUNUAT="$UE5_ROOT/Engine/Build/BatchFiles/RunUAT.bat"
echo "UE5 root : $UE5_ROOT"
echo "RunUAT   : $RUNUAT"

# ── Parse args ────────────────────────────────────────────────────────────────
DO_BUILD=true
DO_INSTALL=false
for arg in "${@:-}"; do
  case "$arg" in
    --install)      DO_INSTALL=true ;;
    --install-only) DO_BUILD=false; DO_INSTALL=true ;;
  esac
done

# ── Resolve APK path (UE5 names it deterministically) ─────────────────────────
APK_PATH="$OUTPUT_DIR/Android_ASTC/HyperMageVR-Android-Development-arm64.apk"

# ── Build ─────────────────────────────────────────────────────────────────────
if [[ "$DO_BUILD" == true ]]; then
  echo ""
  echo "=== Building HyperMage VR APK (Android/Quest 3) ==="
  echo "Output : $OUTPUT_DIR"
  echo ""

  # cygpath -m = mixed mode: drive letter + forward slashes (works in both cmd and PS)
  UPROJECT_WIN=$(cygpath -m "$UPROJECT")
  OUTPUT_WIN=$(cygpath -m "$OUTPUT_DIR")
  RUNUAT_WIN=$(cygpath -m "$RUNUAT")

  mkdir -p "$OUTPUT_DIR"

  # Write a temp .bat file (Unix path for shell writes, mixed path for cmd execution)
  BAT_UNIX="$REPO_ROOT/.run-uat-apk.bat"
  BAT_WIN=$(cygpath -m "$BAT_UNIX")

  # @echo on so RunUAT errors are visible; single long line avoids cmd continuation issues
  printf '@echo on\r\n"%s" BuildCookRun -project="%s" -noP4 -platform=Android -clientconfig=Development -cook -build -stage -pak -cookflavor=ASTC -archive -archivedirectory="%s" -nocompileeditor -log\r\n' \
    "$RUNUAT_WIN" "$UPROJECT_WIN" "$OUTPUT_WIN" > "$BAT_UNIX"

  echo "Running: $BAT_WIN"
  # Use //c (double-slash) to prevent Git Bash from converting /c to a drive path
  cmd //c "$BAT_WIN"
  EXIT_CODE=$?
  rm -f "$BAT_UNIX"

  if [[ $EXIT_CODE -ne 0 ]]; then
    echo "ERROR: RunUAT exited with code $EXIT_CODE" >&2
    exit $EXIT_CODE
  fi

  echo ""
  if [[ -f "$APK_PATH" ]]; then
    APK_SIZE=$(du -sh "$APK_PATH" | cut -f1)
    echo "=== APK built successfully ==="
    echo "  Path : $APK_PATH"
    echo "  Size : $APK_SIZE"
  else
    # UE5 sometimes places APK without the _ASTC suffix — check fallback locations
    FALLBACK=$(find "$OUTPUT_DIR" -name "*.apk" 2>/dev/null | head -1)
    if [[ -n "$FALLBACK" ]]; then
      APK_PATH="$FALLBACK"
      echo "=== APK built (found at alternate path) ==="
      echo "  Path : $APK_PATH"
    else
      echo "ERROR: Build completed but APK not found under $OUTPUT_DIR" >&2
      echo "Check UE5 packaging log above for errors." >&2
      exit 1
    fi
  fi
fi

# ── Install ───────────────────────────────────────────────────────────────────
if [[ "$DO_INSTALL" == true ]]; then
  echo ""
  echo "=== Installing APK on Quest 3 ==="

  if [[ ! -f "$APK_PATH" ]]; then
    # Try to find any APK in the output dir
    FALLBACK=$(find "$OUTPUT_DIR" -name "*.apk" 2>/dev/null | head -1)
    if [[ -n "$FALLBACK" ]]; then
      APK_PATH="$FALLBACK"
    else
      echo "ERROR: No APK found at $APK_PATH" >&2
      echo "Run without --install-only to build first." >&2
      exit 1
    fi
  fi

  echo "Connected devices:"
  "$ADB" devices

  echo ""
  echo "Installing $APK_PATH ..."
  "$ADB" install -r "$(cygpath -w "$APK_PATH")"

  echo ""
  echo "=== Install complete ==="
  echo "Launch from: Quest 3 library → Unknown Sources → HyperMage VR"
fi

echo ""
echo "Done."
