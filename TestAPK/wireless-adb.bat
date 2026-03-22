@echo off
setlocal

set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe

echo.
echo  Hypermage VR — Wireless ADB Setup
echo  ----------------------------------
echo.
echo  Prerequisites on Quest 3:
echo    Settings -^> System -^> Developer -^> Wireless ADB: ON
echo    Settings -^> Wi-Fi -^> (your network) -^> note the IP address
echo.

if "%1"=="" (
    set /p QUEST_IP="  Enter Quest 3 IP address: "
) else (
    set QUEST_IP=%1
)

echo.
echo  Connecting to %QUEST_IP%:5555...
"%ADB%" connect %QUEST_IP%:5555

echo.
echo  Connected devices:
"%ADB%" devices

echo.
echo  Done. Run wireless-install.bat to sideload the APK.
echo.
pause
