@echo on
set ANDROID_HOME=C:/Users/j_e_a/AppData/Local/Android/Sdk
set NDKROOT=C:/Users/j_e_a/AppData/Local/Android/Sdk/ndk/27.2.12479018
set NDK_ROOT=C:/Users/j_e_a/AppData/Local/Android/Sdk/ndk/27.2.12479018
set JAVA_HOME=C:/Program Files/Android/Android Studio1/jbr
set PATH=%JAVA_HOME%\bin;%PATH%
echo === Building Win64 game module for cook step ===
"C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/ThirdParty/DotNet/8.0.412/win-x64/dotnet.exe" "C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll" HyperMageVREditor Win64 Development -Project="C:/Users/j_e_a/OneDrive/Projects/Hypermage/Hypermage_VR/UnrealProject/HyperMageVR.uproject" -NoUBTMakefiles
if ERRORLEVEL 1 exit /b 1
echo === Building and packaging Android APK ===
"C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/RunUAT.bat" BuildCookRun -project="C:/Users/j_e_a/OneDrive/Projects/Hypermage/Hypermage_VR/UnrealProject/HyperMageVR.uproject" -noP4 -platform=Android -clientconfig=Shipping -cook -build -stage -pak -cookflavor=ASTC -archive -archivedirectory="C:/Users/j_e_a/OneDrive/Projects/Hypermage/Hypermage_VR/Packaged/Android" -nocompileeditor -log
