# HyperMage VR - Unreal Engine Project

## Overview

This is the Unreal Engine 5.3+ VR multiplayer project for Meta Quest 3. The project implements a server-authoritative dedicated server architecture with VR comfort settings and player capacity management.

## Requirements

- **Unreal Engine**: 5.3 or later
- **Target Platform**: Meta Quest 3 (Android)
- **Development Platform**: Windows with Visual Studio 2022
- **Plugins Required**:
  - OpenXR
  - OpenXRHandTracking
  - GameLift Server SDK
  - OnlineSubsystem

## Project Structure

```
UnrealProject/
├── HyperMageVR.uproject          # Project file
├── Config/                        # Configuration files
│   ├── DefaultEngine.ini          # Engine settings (OpenXR, Android, networking)
│   ├── DefaultGame.ini            # Game settings (packaging, cooking)
│   └── DefaultInput.ini           # Input mappings (VR controllers)
├── Source/                        # C++ source code
│   ├── HyperMageVR/              # Main game module
│   │   ├── HyperMageVR.Build.cs  # Build configuration
│   │   ├── VRPawn.h/.cpp         # VR player pawn with comfort settings
│   │   ├── HMVRGameMode.h/.cpp   # Server-authoritative game mode
│   │   └── HMVRGameInstance.h/.cpp # Game instance for session management
│   ├── HyperMageVR.Target.cs     # Client build target
│   └── HyperMageVRServer.Target.cs # Dedicated server build target
└── README.md                      # This file
```

## Features Implemented

### 1. VR Pawn with Comfort Settings (Requirements 1.3-1.7)

**File**: `Source/HyperMageVR/VRPawn.h/.cpp`

The VR Pawn implements comprehensive comfort settings to reduce motion sickness:

- **Smooth Locomotion** (default): Continuous movement with speed cap (300 cm/s)
- **Snap Turn** (default): 45-degree instant rotation with cooldown
- **Smooth Turn** (optional): Continuous rotation at 90 degrees/s
- **Comfort Vignette**: Dynamic vignette that appears during acceleration/rotation
- **Teleport** (fallback): Point-and-teleport locomotion up to 1000cm
- **Flight Mode** (optional): Full 3D movement with comfort tuning (500 cm/s)

All comfort settings are replicated and can be configured per-player.

### 2. Server-Authoritative Architecture (Requirement 2.1)

**File**: `Source/HyperMageVR/HMVRGameMode.h/.cpp`

The game mode enforces server authority for all gameplay state:

- All state changes originate from the server
- Client movements are validated before acceptance
- Anti-cheat validation (movement speed, teleport distance)
- Server RPCs for movement and teleportation

### 3. Player Capacity Management (Requirement 2.2)

**File**: `Source/HyperMageVR/HMVRGameMode.h/.cpp`

The game mode enforces player capacity limits:

- **Maximum Players**: 15 per shard
- **Minimum Players**: 10 per shard (for matchmaking)
- Rejects connections when at capacity
- Tracks connected players with cleanup

### 4. JWT Authentication (Requirements 3.1-3.4)

**Files**: `HMVRGameMode.h/.cpp`, `HMVRGameInstance.h/.cpp`

Authentication system for secure player connections:

- JWT token validation in PreLogin
- Token passed via connection URL parameters
- Player ID extraction from token claims
- Connection rejection for invalid/expired tokens

### 5. GameLift Integration (Requirement 2.4)

**File**: `Source/HyperMageVR/HMVRGameMode.h/.cpp`

GameLift Server SDK integration for managed hosting:

- Server initialization and ProcessReady
- Player session validation
- Health reporting every 30 seconds
- Session tracking and management

### 6. Voice Communication System (Requirements 4.1-4.5)

**Files**: `Source/HyperMageVR/VoiceChatInterface.h/.cpp`, `Source/HyperMageVR/MockVoiceProvider.h/.cpp`

Party voice communication system for multiplayer shards:

- **Voice Chat Interface**: Pluggable provider interface for different voice solutions
- **Voice Chat Manager**: Manages party voice channels per shard
- **Mock Voice Provider**: Testing implementation with simulated voice connections
- **Party Voice Routing**: All players in a shard can hear each other
- **Non-Spatial Audio**: Voice is not affected by player position or distance
- **Mute Controls**: Support for microphone muting and per-player muting

All players in a shard join the same party voice channel (`party_<ShardId>`) and can hear all other players regardless of position.

### 7. Session Management and Reward System (Requirements 5.1-5.7, 15.1-15.5)

**Files**: `Source/HyperMageVR/SessionManager.h/.cpp`, `Source/HyperMageVR/RewardSystem.h/.cpp`, `Source/HyperMageVR/SessionAPIClient.h/.cpp`

Ephemeral session management with reward-only persistence:

- **Session Manager**: Manages player session lifecycle with state transitions
- **Session States**: CREATED → ACTIVE → ENDED → EXPIRED
- **Ephemeral Data**: Gameplay events and state are discarded after session end
- **Persistent Data**: Only reward flags persist (stored as boolean with string identifiers)
- **TTL Expiration**: Session and event data expire 72 hours after session end
- **Reward System**: Validates rewards against catalog before granting
- **Error Codes**: `INVALID_REWARD_ID`, `REWARD_CATALOG_NOT_FOUND`, `REWARD_ALREADY_GRANTED`
- **Session API Client**: Stub interface for sending session summaries (actual API in Task 15.4)

The system ensures minimal data storage costs while tracking player achievements.

## Building the Project

### Prerequisites

1. Install Unreal Engine 5.3 or later
2. Install Visual Studio 2022 with C++ game development workload
3. Install Android SDK and NDK for Quest 3 builds
4. Install GameLift Server SDK plugin

### Generate Project Files

```bash
# Right-click HyperMageVR.uproject and select "Generate Visual Studio project files"
# Or use command line:
"C:\Program Files\Epic Games\UE_5.3\Engine\Build\BatchFiles\Build.bat" -projectfiles -project="HyperMageVR.uproject" -game -engine
```

### Build Client (Quest 3)

```bash
# Open HyperMageVR.uproject in Unreal Editor
# File -> Package Project -> Android (ASTC)
# Or use command line:
"C:\Program Files\Epic Games\UE_5.3\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="HyperMageVR.uproject" -platform=Android -clientconfig=Shipping -cook -stage -package -pak
```

### Build Dedicated Server

```bash
# Use command line to build server target:
"C:\Program Files\Epic Games\UE_5.3\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="HyperMageVR.uproject" -platform=Win64 -serverconfig=Shipping -server -noclient -cook -stage -package -pak
```

## Configuration

### VR Comfort Settings

Edit `DefaultEngine.ini` to configure VR settings:

```ini
[/Script/HeadMountedDisplay.HeadMountedDisplaySettings]
bEnableHMDDisplay=True
XRSystemName=OpenXR
```

### Networking

Edit `DefaultEngine.ini` to configure networking:

```ini
[/Script/OnlineSubsystemUtils.IpNetDriver]
NetServerMaxTickRate=60
MaxNetTickRate=60
MaxInternetClientRate=25000
MaxClientRate=25000
```

### Player Capacity

Edit `HMVRGameMode` defaults in Unreal Editor or C++:

```cpp
MaxPlayers = 15;  // Maximum players per shard
MinPlayers = 10;  // Minimum players for matchmaking
```

## Testing

### Property-Based Tests

Three property-based tests validate core requirements:

1. **Server Authority** (`tests/properties/server-authority-gameplay-state.test.ts`)
   - Validates that clients cannot directly modify gameplay state
   - Validates that server can modify and replicate state
   - Validates server-side validation of client requests

2. **Shard Capacity** (`tests/properties/shard-player-capacity-enforcement.test.ts`)
   - Validates 15-player capacity limit
   - Validates connection rejection when full
   - Validates capacity management across disconnections

3. **JWT Validation** (`tests/properties/jwt-token-validation.test.ts`)
   - Validates JWT token signature, expiration, and claims
   - Validates player ID extraction from tokens
   - Validates rejection of invalid/expired tokens

4. **Party Voice Routing** (`tests/properties/party-voice-routing.test.ts`)
   - Validates all players in a shard can hear each other
   - Validates voice is not affected by player position or distance
   - Validates party voice channel management
   - Validates mute controls and channel isolation

5. **Session Ephemeral State** (`tests/properties/session-ephemeral-state.test.ts`)
   - Validates only rewards persist after session ends
   - Validates gameplay state is discarded
   - Validates TTL is set to 72 hours after session end
   - Validates session state transitions (CREATED → ACTIVE → ENDED)
   - Validates events only tracked for ACTIVE sessions

6. **Reward Storage Format** (`tests/properties/reward-storage-format.test.ts`)
   - Validates rewards stored as boolean flags with string identifiers
   - Validates reward records have no TTL (persistent)
   - Validates invalid reward IDs return INVALID_REWARD_ID error
   - Validates catalog loading failures return REWARD_CATALOG_NOT_FOUND error
   - Validates duplicate grants return REWARD_ALREADY_GRANTED error

Run tests:

```bash
npm test -- tests/properties/server-authority-gameplay-state.test.ts --testTimeout=60000
npm test -- tests/properties/shard-player-capacity-enforcement.test.ts --testTimeout=60000
npm test -- tests/properties/jwt-token-validation.test.ts --testTimeout=60000
npm test -- tests/properties/party-voice-routing.test.ts --testTimeout=60000
npm test -- tests/properties/session-ephemeral-state.test.ts --testTimeout=60000
npm test -- tests/properties/reward-storage-format.test.ts --testTimeout=60000
```

### Local Testing

1. **PIE (Play In Editor)**: Test VR functionality in editor
2. **Standalone**: Test client build on Windows
3. **Dedicated Server**: Run server build and connect clients
4. **Quest 3**: Deploy to device via SideQuest or Meta Quest Developer Hub

## Known Limitations

- GameLift SDK integration is stubbed for development (requires AWS deployment)
- JWT validation is simplified (requires Cognito public keys in production)
- Voice communication uses mock provider (requires real voice provider like Vivox or Agora for production)
- Session API client is a stub (actual API implementation in Task 15.4)
- Rewards catalog loaded from local file (should be loaded from S3 or bundled in production)

## Next Steps

See `tasks.md` for remaining implementation tasks:

- Task 13: Session management and reward system ✅ COMPLETE
- Task 14: Checkpoint validation
- Task 15: AWS infrastructure with Terraform

## References

- [Unreal Engine VR Documentation](https://docs.unrealengine.com/5.3/en-US/developing-for-vr-in-unreal-engine/)
- [OpenXR Plugin](https://docs.unrealengine.com/5.3/en-US/openxr-plugin-in-unreal-engine/)
- [Meta Quest Development](https://developer.oculus.com/documentation/unreal/)
- [GameLift Server SDK](https://docs.aws.amazon.com/gamelift/latest/developerguide/integration-engines-unity-using.html)
- [Dedicated Server Guide](https://docs.unrealengine.com/5.3/en-US/setting-up-dedicated-servers-in-unreal-engine/)
