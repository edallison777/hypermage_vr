@echo off
setlocal

set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe
set APK=app\build\outputs\apk\debug\app-debug.apk

echo.
echo  Hypermage VR — Wireless APK Install
echo  -------------------------------------
echo.

if not exist "%APK%" (
    echo  ERROR: APK not found at %APK%
    echo  Build first: Open TestAPK\ in Android Studio, then Build -^> Make Project
    echo.
    pause
    exit /b 1
)

echo  Checking for connected Quest 3...
"%ADB%" devices

echo.
echo  Installing %APK%...
"%ADB%" install -r "%APK%"

if %ERRORLEVEL%==0 (
    echo.
    echo  SUCCESS! App installed. Launch from Unknown Sources in Quest 3 library.
) else (
    echo.
    echo  FAILED. Check Quest is connected: run wireless-adb.bat first.
)

echo.
pause
