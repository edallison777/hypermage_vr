@echo off
setlocal
set ADB=C:\Users\j_e_a\AppData\Local\Android\Sdk\platform-tools\adb.exe
set QUEST_IP=192.168.1.111

echo === HyperMage VR Dev Session Setup ===
echo Connecting to Quest 3 via USB...

%ADB% wait-for-device
for /f "tokens=*" %%d in ('%ADB% devices ^| findstr /v "List" ^| findstr "device$" ^| head -1') do set USB_ID=%%d

echo Enabling wireless ADB...
%ADB% tcpip 5555
timeout /t 4 /nobreak >nul

echo Connecting wirelessly at %QUEST_IP%:5555...
%ADB% connect %QUEST_IP%:5555
timeout /t 2 /nobreak >nul

echo Applying no-proximity-sensor prop...
%ADB% -s %QUEST_IP%:5555 shell "setprop debug.oculus.NoProximitySensor 1"
%ADB% -s %QUEST_IP%:5555 shell "input keyevent 224"
%ADB% -s %QUEST_IP%:5555 shell "am broadcast -a com.oculus.vrpowermanager.action.PROXIMITY_COVERED"

echo.
echo === You can now unplug the USB cable ===
echo Wireless ADB active at %QUEST_IP%:5555
echo.
echo NOTE: If app goes to sleep, run: keep-awake.bat
echo.
pause
