@echo off
setlocal
set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe

echo === Force-stop current instance ===
%ADB% shell "am force-stop com.hypermage.vr"
timeout /t 2 /nobreak >nul

echo === Disable proximity sensor (allow VR without headset proximity) ===
%ADB% shell "setprop debug.oculus.NoProximitySensor 1"

echo === Launch with explicit VR intent (triggers Quest compositor registration) ===
%ADB% shell "am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -c com.oculus.intent.category.VR -n com.hypermage.vr/com.epicgames.unreal.GameActivity"

echo.
echo === Watch VrApi registration: ===
echo   adb logcat -d ^| findstr "PTApiClients"
echo === Watch UE log: ===
echo   adb logcat -s UE
echo === Check log file: ===
echo   adb shell "ls /sdcard/Android/data/com.hypermage.vr/files/UnrealGame/HyperMageVR/HyperMageVR/Saved/Logs/"
echo.
pause
