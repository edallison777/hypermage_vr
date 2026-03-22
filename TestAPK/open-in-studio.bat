@echo off
echo Opening TestAPK in Android Studio...
start "" "C:\Program Files\Android\Android Studio1\bin\studio64.exe" "%~dp0"
echo.
echo Once Android Studio opens:
echo   1. Wait for Gradle sync to finish (it downloads Gradle automatically)
echo   2. Build ^> Make Project
echo   3. The APK will be at: app\build\outputs\apk\debug\app-debug.apk
echo   4. Run wireless-install.bat to sideload it
echo.
