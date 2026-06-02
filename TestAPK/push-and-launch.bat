@echo off
setlocal
set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe
set APK=C:\Users\j_e_a\OneDrive\Projects\Hypermage\Hypermage_VR\Packaged\Android\HyperMageVR-Android-Shipping-arm64.apk
set PAK=C:\Users\j_e_a\OneDrive\Projects\Hypermage\Hypermage_VR\UnrealProject\Saved\StagedBuilds\Android_ASTC\HyperMageVR\Content\Paks\HyperMageVR-Android_ASTC.pak
set AUTOLOGIN=C:\Users\j_e_a\OneDrive\Projects\Hypermage\Hypermage_VR\AutoLogin.txt

set DEV_BASE=/sdcard/Android/data/com.hypermage.vr/files
set DEV_GAME=%DEV_BASE%/UnrealGame/HyperMageVR/HyperMageVR

echo === Step 1: Install APK (preserve data with -r) ===
%ADB% install -r "%APK%"
if ERRORLEVEL 1 (
    echo WARN: -r install failed, trying fresh install...
    %ADB% uninstall com.hypermage.vr
    %ADB% install "%APK%"
)

echo === Step 2: Create directories ===
%ADB% shell "mkdir -p %DEV_GAME%/Content/Paks"
%ADB% shell "mkdir -p %DEV_GAME%/Saved"

echo === Step 3: Push PAK (65MB, ~30s) ===
%ADB% push "%PAK%" "%DEV_GAME%/Content/Paks/HyperMageVR-Android_ASTC.pak"
if ERRORLEVEL 1 (echo ERROR: PAK push failed & exit /b 1)

echo === Step 4: Push UECommandLine.txt (-log for Shipping builds) ===
%ADB% shell "echo -log > %DEV_BASE%/UECommandLine.txt"

echo === Step 5: Push AutoLogin.txt ===
%ADB% push "%AUTOLOGIN%" "%DEV_GAME%/Saved/AutoLogin.txt"

echo === Step 6: Launch app (VR intent — required for Quest compositor to register the app) ===
%ADB% shell "setprop debug.oculus.NoProximitySensor 1"
%ADB% shell "am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -c com.oculus.intent.category.VR -n com.hypermage.vr/com.epicgames.unreal.GameActivity"

echo.
echo === All done. App launched. ===
echo Watch for log file at: %DEV_GAME%/Saved/Logs/HyperMageVR.log
echo Check with: adb logcat -s UE
echo.
pause
