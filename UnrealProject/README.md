# UnrealProject - VR Multiplayer Game Implementation

## Overview

The UnrealProject directory contains the Unreal Engine 5.3+ VR multiplayer game implementation targeting Meta Quest 3 devices. The project implements a dedicated server architecture with comprehensive VR comfort settings, party voice communication, and server-authoritative gameplay systems.

## Project Structure

```
UnrealProject/
├── Config/                    # Engine and project configuration
│   ├── DefaultEngine.ini     # Engine settings, VR configuration
│   ├── DefaultGame.ini       # Game-specific settings
│   └── DefaultInput.ini      # Input bindings for VR controllers
├── Content/                   # Game content (Blueprints, Maps, Assets)
│   ├── Maps/                 # Level files (.umap)
│   ├── Blueprints/           # Blueprint classes
│   ├── Materials/            # Material assets
│   └── Audio/                # Audio assets
├── Source/                    # C++ source code
│   └── HyperMageVR/          # Main game module
│       ├── HyperMageVR.Build.cs      # Build configuration
│       ├── HyperMageVR.cpp           # Module implementation
│       ├── HyperMageVR.h             # Module header
│       ├── HMVRGameMode.cpp/.h       # Server game mode
│       ├── HMVRGameInstance.cpp/.h   # Game instance
│       ├── VRPawn.cpp/.h             # VR player pawn
│       ├── SessionManager.cpp/.h     # Session management
│       ├── RewardSystem.cpp/.h       # Reward granting system
│       ├── VoiceChatInterface.cpp/.h # Voice communication
│       └── JWTValidator.cpp/.h       # Authentication
└── HyperMageVR.uproject      # Project file
```

## Key Features

### VR Platform Support
- **Target Platform**: Meta Quest 3 with OpenXR API
- **Comfort Settings**: Snap turn, comfort vignette, teleport fallback
- **Locomotion**: Smooth movement with speed caps and comfort options
- **Hand Tracking**: Full VR controller support with gesture recognition

### Multiplayer Architecture
- **Dedicated Server**: Server-authoritative gameplay with client prediction
- **Player Capacity**: 10-15 players per shard with connection validation
- **GameLift Integration**: AWS GameLift for fleet management and matchmaking
- **Network Optimization**: Bandwidth management for VR performance requirements

### Authentication & Security
- **JWT Validation**: AWS Cognito token validation on server
- **Server Authority**: All gameplay actions validated server-side
- **Anti-Cheat**: Server-side validation prevents client manipulation

### Voice Communication
- **Party Voice**: All players in shard can communicate
- **Pluggable Provider**: Interface supports multiple voice providers
- **Mock Provider**: Testing implementation for development

### Session Management
- **Ephemeral Sessions**: Gameplay state discarded after session end
- **Reward Persistence**: Only reward flags persist beyond session
- **TTL Management**: Automatic data expiration after 72 hours

## Core Classes

### HMVRGameMode (Server-Side Game Logic)

```cpp
UCLASS()
class HYPERMAGEVR_API AHMVRGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AHMVRGameMode();

    // Player connection management
    virtual void PreLogin(const FString& Options, const FString& Address, 
                         const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual APlayerController* Login(UPlayer* NewPlayer, ENetRole InRemoteRole, 
                                   const FString& Portal, const FString& Options, 
                                   const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual void Logout(AController* Exiting) override;

    // Session management
    UFUNCTION(BlueprintCallable)
    void StartGameSession();
    
    UFUNCTION(BlueprintCallable)
    void EndGameSession();

    // Reward system
    UFUNCTION(BlueprintCallable)
    bool GrantReward(const FString& PlayerId, const FString& RewardId);

protected:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    int32 MaxPlayers = 15;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    float SessionTimeoutMinutes = 30.0f;

private:
    TArray<FString> ConnectedPlayerIds;
    class USessionManager* SessionManager;
    class URewardSystem* RewardSystem;
    class UJWTValidator* JWTValidator;
};
```

### VRPawn (VR Player Character)

```cpp
UCLASS()
class HYPERMAGEVR_API AVRPawn : public APawn
{
    GENERATED_BODY()

public:
    AVRPawn();

protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    // VR Components
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
    class UCameraComponent* VRCamera;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
    class UMotionControllerComponent* LeftController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
    class UMotionControllerComponent* RightController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
    class UStaticMeshComponent* LeftControllerMesh;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
    class UStaticMeshComponent* RightControllerMesh;

    // Locomotion settings
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Locomotion")
    float MovementSpeed = 300.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Locomotion")
    bool bSnapTurnEnabled = true;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Locomotion")
    float SnapTurnAngle = 45.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Locomotion")
    bool bComfortVignetteEnabled = true;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Locomotion")
    bool bTeleportEnabled = true;

    // Input handlers
    UFUNCTION()
    void MoveForward(float Value);

    UFUNCTION()
    void MoveRight(float Value);

    UFUNCTION()
    void SnapTurnRight();

    UFUNCTION()
    void SnapTurnLeft();

    UFUNCTION()
    void StartTeleport();

    UFUNCTION()
    void EndTeleport();

    // Networking
    UFUNCTION(Server, Reliable)
    void ServerMoveForward(float Value);

    UFUNCTION(Server, Reliable)
    void ServerMoveRight(float Value);

    UFUNCTION(Server, Reliable)
    void ServerTeleport(FVector Location);

private:
    FVector TeleportDestination;
    bool bIsTeleporting = false;
};
```

### SessionManager (Session Lifecycle)

```cpp
UCLASS()
class HYPERMAGEVR_API USessionManager : public UObject
{
    GENERATED_BODY()

public:
    USessionManager();

    // Session lifecycle
    UFUNCTION(BlueprintCallable)
    FString CreateSession(const TArray<FString>& PlayerIds);

    UFUNCTION(BlueprintCallable)
    bool StartSession(const FString& SessionId);

    UFUNCTION(BlueprintCallable)
    bool EndSession(const FString& SessionId);

    // Event tracking
    UFUNCTION(BlueprintCallable)
    void RecordInteractionEvent(const FString& SessionId, const FString& PlayerId, 
                               const FString& EventType, const FString& EventData);

    // Session queries
    UFUNCTION(BlueprintCallable)
    bool IsSessionActive(const FString& SessionId) const;

    UFUNCTION(BlueprintCallable)
    TArray<FString> GetSessionPlayerIds(const FString& SessionId) const;

protected:
    UPROPERTY()
    TMap<FString, FSessionData> ActiveSessions;

private:
    struct FSessionData
    {
        FString SessionId;
        TArray<FString> PlayerIds;
        ESessionState State;
        FDateTime StartTime;
        FDateTime EndTime;
        TArray<FInteractionEvent> Events;
    };

    enum class ESessionState : uint8
    {
        Created,
        Active,
        Ended,
        Expired
    };
};
```

### RewardSystem (Achievement Management)

```cpp
UCLASS()
class HYPERMAGEVR_API URewardSystem : public UObject
{
    GENERATED_BODY()

public:
    URewardSystem();

    // Reward management
    UFUNCTION(BlueprintCallable)
    bool GrantReward(const FString& PlayerId, const FString& RewardId);

    UFUNCTION(BlueprintCallable)
    bool HasReward(const FString& PlayerId, const FString& RewardId) const;

    UFUNCTION(BlueprintCallable)
    TArray<FString> GetPlayerRewards(const FString& PlayerId) const;

    // Catalog management
    UFUNCTION(BlueprintCallable)
    bool LoadRewardsCatalog(const FString& CatalogPath);

    UFUNCTION(BlueprintCallable)
    bool IsValidRewardId(const FString& RewardId) const;

protected:
    UPROPERTY()
    TMap<FString, TArray<FString>> PlayerRewards;

    UPROPERTY()
    TArray<FRewardDefinition> RewardsCatalog;

private:
    struct FRewardDefinition
    {
        FString Id;
        FString Name;
        FString Description;
        FString Category;
    };

    // Error codes
    static const FString INVALID_REWARD_ID;
    static const FString REWARD_CATALOG_NOT_FOUND;
    static const FString REWARD_ALREADY_GRANTED;
};
```

### VoiceChatInterface (Party Voice Communication)

```cpp
UCLASS()
class HYPERMAGEVR_API UVoiceChatInterface : public UObject
{
    GENERATED_BODY()

public:
    UVoiceChatInterface();

    // Voice chat management
    UFUNCTION(BlueprintCallable)
    bool InitializeVoiceChat(const FString& ChannelName);

    UFUNCTION(BlueprintCallable)
    bool JoinVoiceChannel(const FString& PlayerId, const FString& ChannelName);

    UFUNCTION(BlueprintCallable)
    bool LeaveVoiceChannel(const FString& PlayerId, const FString& ChannelName);

    UFUNCTION(BlueprintCallable)
    bool MutePlayer(const FString& PlayerId, bool bMuted);

    UFUNCTION(BlueprintCallable)
    bool BlockPlayer(const FString& PlayerId, bool bBlocked);

    // Provider interface
    UFUNCTION(BlueprintCallable)
    void SetVoiceProvider(TScriptInterface<IVoiceProvider> Provider);

protected:
    UPROPERTY()
    TScriptInterface<IVoiceProvider> VoiceProvider;

    UPROPERTY()
    TMap<FString, TArray<FString>> ChannelMembers;

private:
    bool bInitialized = false;
    FString CurrentChannelName;
};

// Voice provider interface
UINTERFACE(BlueprintType)
class UVoiceProvider : public UInterface
{
    GENERATED_BODY()
};

class IVoiceProvider
{
    GENERATED_BODY()

public:
    virtual bool ConnectToChannel(const FString& ChannelName) = 0;
    virtual bool DisconnectFromChannel(const FString& ChannelName) = 0;
    virtual bool RouteAudio(const FString& FromPlayerId, const FString& ToPlayerId) = 0;
    virtual bool SetMuted(const FString& PlayerId, bool bMuted) = 0;
};
```

## Configuration

### DefaultEngine.ini

```ini
[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Game/Maps/MainMenu
ServerDefaultMap=/Game/Maps/DefaultLevel
GameInstanceClass=/Script/HyperMageVR.HMVRGameInstance

[/Script/Engine.Engine]
+ActiveGameNameRedirects=(OldGameName="TP_VirtualRealityBP",NewGameName="/Script/HyperMageVR")
+ActiveGameNameRedirects=(OldGameName="/Script/TP_VirtualRealityBP",NewGameName="/Script/HyperMageVR")

[/Script/HardwareTargeting.HardwareTargetingSettings]
TargetedHardwareClass=Mobile
AppliedTargetedHardwareClass=Mobile
DefaultGraphicsPerformance=Scalable
AppliedDefaultGraphicsPerformance=Scalable

[/Script/Engine.RendererSettings]
r.Mobile.DisableVertexFog=True
r.Shadow.CSM.MaxCascades=1
r.MobileMSAA=1
r.Mobile.UseLegacyShadingModel=False
r.Mobile.UseHWsRGBEncoding=False

[/Script/OpenXRInput.OpenXRInputSettings]
ActionManifestURL=/Game/VR/OpenXRActionManifest.json

[/Script/AndroidRuntimeSettings.AndroidRuntimeSettings]
PackageName=com.hypermagevr.game
ApplicationDisplayName=HyperMage VR
VersionDisplayName=1.0.0
MinSDKVersion=29
TargetSDKVersion=33
InstallLocation=InternalOnly
bPackageDataInsideApk=True

[/Script/GameLiftServerSDK.GameLiftServerSDKSettings]
bEnabled=True
ServerParameters=-log
```

### DefaultGame.ini

```ini
[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Game/Maps/MainMenu
ServerDefaultMap=/Game/Maps/DefaultLevel

[/Script/UnrealEd.ProjectPackagingSettings]
Build=IfProjectHasCode
BuildConfiguration=PPBC_Development
StagingDirectory=(Path="")
FullRebuild=False
ForDistribution=False
IncludeDebugFiles=False
BlueprintNativizationMethod=Disabled
bIncludeNativizedAssetsInProjectGeneration=False
bExcludeMonolithicEngineHeadersInNativizedCode=False
UsePakFile=True
bGenerateChunks=False
bBuildHttpChunkInstallData=False
HttpChunkInstallDataDirectory=(Path="")
HttpChunkInstallDataVersion=
IncludePrerequisites=True
IncludeAppLocalPrerequisites=False
bShareMaterialShaderCode=True
bSharedMaterialNativeLibraries=True
ApplocalPrerequisitesDirectory=(Path="")
IncludeCrashReporter=False
InternationalizationPreset=English
-CulturesToStage=en
+CulturesToStage=en
bCookAll=False
bCookMapsOnly=False
bCompressed=True
```

## Build System

### Cloud Build Process

The project uses cloud-based builds on AWS EC2 instances:

1. **Build Trigger**: UnrealMCP adapter receives build request
2. **EC2 Launch**: g4dn.xlarge instance with UE5.3 AMI
3. **Project Clone**: Repository cloned to build instance
4. **Compilation**: C++ code compiled, content cooked
5. **Packaging**: Client (Quest 3) and server builds packaged
6. **Artifact Upload**: Build outputs uploaded to S3
7. **Instance Termination**: EC2 instance terminated to minimize costs

### Local Build (Optional)

For developers with UE5.3+ installed locally:

```bash
# Build Development configuration
/path/to/UnrealEngine/Engine/Build/BatchFiles/RunUAT.bat BuildCookRun \
  -project=HyperMageVR.uproject \
  -platform=Android \
  -configuration=Development \
  -cook -build -stage -package

# Build Server configuration
/path/to/UnrealEngine/Engine/Build/BatchFiles/RunUAT.bat BuildCookRun \
  -project=HyperMageVR.uproject \
  -platform=Linux \
  -configuration=Development \
  -cook -build -stage -package -server -noclient
```

### Build Configuration

```cpp
// HyperMageVR.Build.cs
using UnrealBuildTool;

public class HyperMageVR : ModuleRules
{
    public HyperMageVR(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject", 
            "Engine",
            "InputCore",
            "HeadMountedDisplay",
            "MotionController",
            "XRBase",
            "OpenXRHMD",
            "GameLiftServerSDK",
            "VoiceChat",
            "OnlineSubsystem",
            "OnlineSubsystemUtils",
            "Json",
            "JsonUtilities",
            "HTTP"
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            "Slate",
            "SlateCore",
            "UMG",
            "Networking",
            "Sockets",
            "PacketHandler"
        });

        if (Target.Type == TargetType.Server)
        {
            PublicDependencyModuleNames.Add("GameLiftServerSDK");
        }

        // VR platform specific
        if (Target.Platform == UnrealTargetPlatform.Android)
        {
            PublicDependencyModuleNames.AddRange(new string[] {
                "AndroidPermission",
                "AndroidRuntimeSettings"
            });
        }
    }
}
```

## Testing

### Unit Tests

```cpp
// Tests/VRPawnTest.cpp
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "VRPawn.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVRPawnMovementTest, "HyperMageVR.VRPawn.Movement",
    EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)

bool FVRPawnMovementTest::RunTest(const FString& Parameters)
{
    // Create test world
    UWorld* TestWorld = UWorld::CreateWorld(EWorldType::Game, false);
    
    // Spawn VR pawn
    AVRPawn* TestPawn = TestWorld->SpawnActor<AVRPawn>();
    TestThis->TestNotNull("VR Pawn should be created", TestPawn);
    
    // Test movement
    FVector InitialLocation = TestPawn->GetActorLocation();
    TestPawn->MoveForward(1.0f);
    
    // Verify movement occurred
    FVector NewLocation = TestPawn->GetActorLocation();
    TestThis->TestTrue("Pawn should move forward", !NewLocation.Equals(InitialLocation));
    
    // Cleanup
    TestWorld->DestroyWorld(false);
    return true;
}
```

### Property-Based Tests

```cpp
// Tests/SessionManagerPropertyTest.cpp
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "SessionManager.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSessionEphemeralStateTest, "HyperMageVR.Session.EphemeralState",
    EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)

bool FSessionEphemeralStateTest::RunTest(const FString& Parameters)
{
    USessionManager* SessionManager = NewObject<USessionManager>();
    
    // Property: After session ends, only rewards should persist
    for (int32 i = 0; i < 100; ++i)
    {
        // Generate random session data
        TArray<FString> PlayerIds = GenerateRandomPlayerIds();
        FString SessionId = SessionManager->CreateSession(PlayerIds);
        
        // Start session and record events
        SessionManager->StartSession(SessionId);
        RecordRandomEvents(SessionManager, SessionId, PlayerIds);
        
        // Grant some rewards
        GrantRandomRewards(SessionId, PlayerIds);
        
        // End session
        SessionManager->EndSession(SessionId);
        
        // Verify only rewards persist
        VerifyOnlyRewardsPersist(SessionId, PlayerIds);
    }
    
    return true;
}
```

## Deployment

### GameLift Deployment

The server build is deployed to AWS GameLift:

```json
{
  "fleetName": "vr-multiplayer-prod",
  "buildId": "build-abc123",
  "instanceType": "c5.large",
  "maxInstances": 3,
  "locations": ["eu-west-1a", "eu-west-1b"],
  "runtimeConfiguration": {
    "serverProcesses": [
      {
        "launchPath": "/local/game/HyperMageVRServer",
        "parameters": "-log",
        "concurrentExecutions": 1
      }
    ],
    "maxConcurrentGameSessionActivations": 1,
    "gameSessionActivationTimeoutSeconds": 300
  }
}
```

### Client Deployment

Quest 3 builds are distributed via:

1. **Development**: Direct APK installation via ADB
2. **Testing**: Internal distribution via Meta Developer Hub
3. **Production**: Meta Quest Store (future)

## Performance Optimization

### Quest 3 Specific Optimizations

- **Rendering**: Mobile rendering pipeline with optimized shaders
- **LOD System**: Aggressive LOD switching for distant objects
- **Occlusion Culling**: VR-optimized culling for stereo rendering
- **Texture Streaming**: Reduced texture memory usage
- **Physics**: Simplified collision for non-critical objects

### Network Optimization

- **Replication**: Only replicate essential gameplay data
- **Compression**: Network packet compression enabled
- **Prediction**: Client-side prediction for movement
- **Interpolation**: Smooth interpolation for remote players

## Troubleshooting

### Common Build Issues

#### Android SDK Not Found
```bash
# Set Android SDK path in Project Settings
# Or set environment variable
export ANDROID_HOME=/path/to/android-sdk
```

#### GameLift SDK Linking Errors
```cpp
// Ensure GameLift SDK is properly linked in Build.cs
if (Target.Type == TargetType.Server)
{
    PublicDependencyModuleNames.Add("GameLiftServerSDK");
}
```

#### VR Not Working on Quest 3
```ini
# Verify OpenXR settings in DefaultEngine.ini
[/Script/OpenXRInput.OpenXRInputSettings]
ActionManifestURL=/Game/VR/OpenXRActionManifest.json

# Check Android manifest permissions
<uses-permission android:name="android.permission.CAMERA" />
<uses-feature android:name="android.hardware.vr.headtracking" android:required="true" />
```

### Performance Issues

#### Low Frame Rate on Quest 3
- Check GPU profiler for bottlenecks
- Reduce texture resolution
- Optimize material complexity
- Enable fixed foveated rendering

#### Network Lag
- Verify server tick rate (60Hz recommended)
- Check bandwidth usage
- Optimize replication frequency
- Enable network compression

This Unreal Engine project provides a complete VR multiplayer foundation with comprehensive systems for authentication, session management, voice communication, and reward tracking, all optimized for Meta Quest 3 deployment.