@echo off
set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe
set QUEST_IP=192.168.1.111

echo Keeping Quest 3 awake (Ctrl+C to stop)...
:loop
%ADB% -s %QUEST_IP%:5555 shell "am broadcast -a com.oculus.vrpowermanager.action.PROXIMITY_COVERED" >nul 2>&1
if errorlevel 1 (
    echo Reconnecting wireless ADB...
    %ADB% connect %QUEST_IP%:5555 >nul 2>&1
    %ADB% -s %QUEST_IP%:5555 shell "input keyevent 224" >nul 2>&1
    %ADB% -s %QUEST_IP%:5555 shell "am broadcast -a com.oculus.vrpowermanager.action.PROXIMITY_COVERED" >nul 2>&1
)
timeout /t 10 /nobreak >nul
goto loop
