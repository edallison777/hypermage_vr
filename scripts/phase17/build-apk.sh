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
# UE5.6 places the APK directly in OUTPUT_DIR (not Android_ASTC subdirectory).
# The AFS_* companion file must be excluded — it is not a runnable APK.
APK_PATH="$OUTPUT_DIR/HyperMageVR-Android-Shipping-arm64.apk"

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

  # Kill stale Java/Gradle daemons
  echo "Stopping any stale Gradle daemons..."
  powershell.exe -Command "Get-Process -Name 'java' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" 2>/dev/null || true

  # Redirect OneDrive-watched directories to local temp via junctions.
  # OneDrive locks files on write (reparse points, placeholders) causing
  # 'Access denied' or 'Unable to delete directory' failures mid-build.
  # Junctions make UE/Gradle write to C:\Temp instead.

  # ── Gradle junction ────────────────────────────────────────────────────────
  GRADLE_DIR="$REPO_ROOT/UnrealProject/Intermediate/Android/arm64/gradle"
  GRADLE_DIR_WIN=$(cygpath -w "$GRADLE_DIR")
  GRADLE_TEMP_WIN="C:\\Temp\\hypermage-gradle"

  echo "Redirecting Gradle dir to local temp..."
  powershell.exe -Command "
    \$g = '$GRADLE_DIR_WIN'
    if (Test-Path \$g) {
      \$attr = (Get-Item \$g -Force).Attributes
      if (\$attr -band [System.IO.FileAttributes]::ReparsePoint) {
        Remove-Item \$g -Force -ErrorAction SilentlyContinue
      } else {
        Remove-Item \$g -Recurse -Force -ErrorAction SilentlyContinue
      }
    }
    if (Test-Path '$GRADLE_TEMP_WIN') { Remove-Item '$GRADLE_TEMP_WIN' -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force '$GRADLE_TEMP_WIN' | Out-Null
    New-Item -ItemType Directory -Force (Split-Path '$GRADLE_DIR_WIN') | Out-Null
  " 2>/dev/null || true

  JLINK_BAT_UNIX="$REPO_ROOT/.run-mklink.bat"
  printf '@echo off\r\nif exist "%s" rmdir "%s" 2>NUL\r\nif exist "%s" rmdir /s /q "%s"\r\nmklink /J "%s" "%s"\r\n' \
    "$GRADLE_DIR_WIN" "$GRADLE_DIR_WIN" \
    "$GRADLE_DIR_WIN" "$GRADLE_DIR_WIN" \
    "$GRADLE_DIR_WIN" "$GRADLE_TEMP_WIN" > "$JLINK_BAT_UNIX"
  cmd //c "$(cygpath -m "$JLINK_BAT_UNIX")"
  rm -f "$JLINK_BAT_UNIX"

  # ── StagedBuilds junction ──────────────────────────────────────────────────
  # OpenXR ships OneDrive placeholder directories inside arm64-v8a; when UE
  # tries to delete StagedBuilds between builds it gets 'Access denied' on
  # those placeholders.  A junction moves the whole StagedBuilds tree to C:\Temp.
  STAGED_DIR="$REPO_ROOT/UnrealProject/Saved/StagedBuilds"
  STAGED_DIR_WIN=$(cygpath -w "$STAGED_DIR")
  STAGED_TEMP_WIN="C:\\Temp\\hypermage-staged"

  echo "Redirecting StagedBuilds to local temp..."
  powershell.exe -Command "
    \$s = '$STAGED_DIR_WIN'
    if (Test-Path \$s) {
      \$attr = (Get-Item \$s -Force).Attributes
      if (\$attr -band [System.IO.FileAttributes]::ReparsePoint) {
        Remove-Item \$s -Force -ErrorAction SilentlyContinue
      } else {
        cmd.exe /c \"rmdir /s /q \$s\" 2>&1 | Out-Null
      }
    }
    if (Test-Path '$STAGED_TEMP_WIN') { cmd.exe /c \"rmdir /s /q $STAGED_TEMP_WIN\" 2>&1 | Out-Null }
    New-Item -ItemType Directory -Force '$STAGED_TEMP_WIN' | Out-Null
    New-Item -ItemType Directory -Force (Split-Path '$STAGED_DIR_WIN') | Out-Null
  " 2>/dev/null || true

  JLINK2_BAT_UNIX="$REPO_ROOT/.run-mklink2.bat"
  printf '@echo off\r\nif exist "%s" rmdir "%s" 2>NUL\r\nif exist "%s" rmdir /s /q "%s"\r\nmklink /J "%s" "%s"\r\n' \
    "$STAGED_DIR_WIN" "$STAGED_DIR_WIN" \
    "$STAGED_DIR_WIN" "$STAGED_DIR_WIN" \
    "$STAGED_DIR_WIN" "$STAGED_TEMP_WIN" > "$JLINK2_BAT_UNIX"
  cmd //c "$(cygpath -m "$JLINK2_BAT_UNIX")"
  rm -f "$JLINK2_BAT_UNIX"

  # Write a temp .bat file (Unix path for shell writes, mixed path for cmd execution)
  BAT_UNIX="$REPO_ROOT/.run-uat-apk.bat"
  BAT_WIN=$(cygpath -m "$BAT_UNIX")

  # Resolve NDK path — prefer the version SetupAndroid.bat installed
  NDK_PATH=$(ls -d "C:/Users/j_e_a/AppData/Local/Android/Sdk/ndk/"* 2>/dev/null | sort -V | tail -1)
  NDK_WIN=$(cygpath -m "$NDK_PATH")
  SDK_WIN="C:/Users/j_e_a/AppData/Local/Android/Sdk"

  JAVA_HOME_WIN="C:/Program Files/Android/Android Studio1/jbr"
  UBT_WIN=$(cygpath -m "$UE5_ROOT/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll")
  DOTNET_WIN=$(cygpath -m "$UE5_ROOT/Engine/Binaries/ThirdParty/DotNet/8.0.300/win-x64/dotnet.exe")

  # @echo on so RunUAT errors are visible; set SDK env vars so UBT finds them even in a stale shell
  # Step 1: compile HyperMageVREditor for Win64 so the editor can load UnrealEditor-HyperMageVR.dll during the cook step
  # Step 2: full Android BuildCookRun (build + cook + stage + pak + archive)
  printf '@echo on\r\nset ANDROID_HOME=%s\r\nset NDKROOT=%s\r\nset NDK_ROOT=%s\r\nset JAVA_HOME=%s\r\nset PATH=%%JAVA_HOME%%\\bin;%%PATH%%\r\necho === Building Win64 game module for cook step ===\r\n"%s" "%s" HyperMageVREditor Win64 Development -Project="%s" -NoUBTMakefiles\r\nif ERRORLEVEL 1 exit /b 1\r\necho === Building and packaging Android APK ===\r\n"%s" BuildCookRun -project="%s" -noP4 -platform=Android -clientconfig=Shipping -cook -build -stage -pak -cookflavor=ASTC -archive -archivedirectory="%s" -nocompileeditor -log\r\n' \
    "$SDK_WIN" "$NDK_WIN" "$NDK_WIN" "$JAVA_HOME_WIN" \
    "$DOTNET_WIN" "$UBT_WIN" "$UPROJECT_WIN" \
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
    # UE5 sometimes places APK at alternate locations — exclude AFS_ companion files
    FALLBACK=$(find "$OUTPUT_DIR" -name "*.apk" ! -name "AFS_*" 2>/dev/null | head -1)
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
