@echo on
echo === Pausing OneDrive to prevent file locks during Gradle build ===
taskkill /f /im OneDrive.exe 2>nul

echo === Preparing custom staging directory outside OneDrive ===
powershell -NoProfile -Command "if(Test-Path 'C:\UEStaged\Stage'){Get-ChildItem 'C:\UEStaged\Stage' -Recurse -Force | ForEach-Object { try{$_.Attributes='Normal'}catch{} }; Remove-Item 'C:\UEStaged\Stage' -Recurse -Force -ErrorAction SilentlyContinue}; New-Item -ItemType Directory -Path 'C:\UEStaged\Stage' -Force | Out-Null; Write-Host 'Stage dir ready.'"

set ANDROID_HOME=C:/Users/j_e_a/AppData/Local/Android/Sdk
set NDKROOT=C:/Users/j_e_a/AppData/Local/Android/Sdk/ndk/27.2.12479018
set NDK_ROOT=C:/Users/j_e_a/AppData/Local/Android/Sdk/ndk/27.2.12479018
set JAVA_HOME=C:/Program Files/Android/Android Studio1/jbr
set PATH=%JAVA_HOME%\bin;%PATH%
echo === Building and packaging Android APK ===
"C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/RunUAT.bat" BuildCookRun -project="C:/Users/j_e_a/OneDrive/Projects/Hypermage/Hypermage_VR/UnrealProject/HyperMageVR.uproject" -noP4 -platform=Android -clientconfig=Development -cook -build -stage -pak -cookflavor=ASTC -nocompileeditor -stagingdirectory="C:\UEStaged\Stage" -log
