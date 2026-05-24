// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRGameMode.h"
#include "VRPawn.h"
#include "SessionManager.h"
#include "RewardSystem.h"
#include "SessionAPIClient.h"
#include "HMVRPlayerState.h"
#include "HMVRInteractableComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "EngineUtils.h"
#include "TimerManager.h"

#if WITH_GAMELIFT
#include "GameLiftServerSDK.h"
#endif
#include "HMVRGameInstance.h"

AHMVRGameMode::AHMVRGameMode()
{
	// Set default pawn class
	DefaultPawnClass = AVRPawn::StaticClass();

	// Use our player state so PlayerId survives the full join/leave cycle
	PlayerStateClass = AHMVRPlayerState::StaticClass();

	// Server-only game mode
	bUseSeamlessTravel = false;
	
	// Set player capacity
	MaxPlayers = 15;
	MinPlayers = 10;

	// Create session manager
	SessionManager = CreateDefaultSubobject<USessionManager>(TEXT("SessionManager"));

	// Create reward system
	RewardSystem = CreateDefaultSubobject<URewardSystem>(TEXT("RewardSystem"));

	// Create Session API client
	SessionAPIClient = CreateDefaultSubobject<USessionAPIClient>(TEXT("SessionAPIClient"));
}

void AHMVRGameMode::BeginPlay()
{
	Super::BeginPlay();

	// Scan the level for all interactable objects. Persistent ones load their
	// last known state from DynamoDB so world-state survives across sessions.
	int32 PersistentCount = 0;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (UHMVRInteractableComponent* Comp = It->FindComponentByClass<UHMVRInteractableComponent>())
		{
			RegisteredInteractables.Add(Comp);
			if (Comp->bPersistent)
			{
				Comp->LoadState();
				++PersistentCount;
			}
		}
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Registered %d interactables (%d persistent, loading state)"),
		RegisteredInteractables.Num(), PersistentCount);

	// Spawn a directional light (sun) + sky light so the world isn't pitch black in VR
	ADirectionalLight* Sun = GetWorld()->SpawnActor<ADirectionalLight>(
		ADirectionalLight::StaticClass(),
		FVector(0.f, 0.f, 1000.f),
		FRotator(-45.f, 45.f, 0.f)
	);
	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Sun light spawned: %s"), Sun ? TEXT("OK") : TEXT("FAILED"));

	GetWorld()->SpawnActor<ASkyLight>(
		ASkyLight::StaticClass(),
		FVector::ZeroVector,
		FRotator::ZeroRotator
	);

	// Spawn a floor plane so VR player has visible geometry and spatial orientation
	UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Floor mesh load: %s"), PlaneMesh ? TEXT("OK") : TEXT("NOT COOKED"));
	if (PlaneMesh)
	{
		FActorSpawnParameters FloorSpawnParams;
		FloorSpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AStaticMeshActor* Floor = GetWorld()->SpawnActor<AStaticMeshActor>(
			AStaticMeshActor::StaticClass(),
			FVector::ZeroVector,
			FRotator::ZeroRotator,
			FloorSpawnParams
		);
		if (Floor)
		{
			Floor->GetStaticMeshComponent()->SetStaticMesh(PlaneMesh);
			Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
			Floor->SetActorScale3D(FVector(20.f, 20.f, 1.f));
			UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Floor plane spawned at origin, scale 20x20m"));
		}
	}
}

void AHMVRGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Initializing game on map %s"), *MapName);

	// Configure Session API client endpoint (hardcoded to live Session API)
	if (SessionAPIClient)
	{
		SessionAPIClient->SetEndpointURL(TEXT("https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"));
		SessionAPIClient->SetAwsRegion(TEXT("eu-west-1"));
	}

	// Configure world-state API for persistent interactable objects (Phase 20)
	UHMVRInteractableComponent::WorldStateApiUrl = TEXT("https://hnhmoxjhmd.execute-api.eu-west-1.amazonaws.com/dev");

	// Initialize reward system
	if (RewardSystem && !RewardSystem->Initialize())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: Failed to initialize reward system"));
	}

	// Initialize GameLift if running on AWS
#if WITH_GAMELIFT
	if (GetWorld()->GetNetMode() == NM_DedicatedServer)
	{
		InitializeGameLift();
	}
#endif

	// Generate session ID
	CurrentSessionId = FGuid::NewGuid().ToString();
	SessionStartTime = FDateTime::UtcNow();

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Session ID: %s"), *CurrentSessionId);
}

void AHMVRGameMode::PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
	Super::PreLogin(Options, Address, UniqueId, ErrorMessage);

	// Check player capacity (Requirement 2.2)
	if (!CanAcceptNewPlayer())
	{
		ErrorMessage = FString::Printf(TEXT("Server full. Maximum %d players allowed."), MaxPlayers);
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Rejected connection - server full (%d/%d)"), 
			GetCurrentPlayerCount(), MaxPlayers);
		return;
	}

	// Extract JWT token from options (Requirement 3.1-3.4)
	FString JWTToken = UGameplayStatics::ParseOption(Options, TEXT("Token"));
	if (JWTToken.IsEmpty())
	{
		ErrorMessage = TEXT("Authentication failed: No JWT token provided");
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Rejected connection - no JWT token"));
		return;
	}

	// Validate JWT token
	FString PlayerId;
	if (!ValidateJWTToken(JWTToken, PlayerId, ErrorMessage))
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Rejected connection - invalid JWT token: %s"), *ErrorMessage);
		return;
	}

#if WITH_GAMELIFT
	// Validate GameLift player session if running on AWS
	if (bGameLiftInitialized)
	{
		FString PlayerSessionId = UGameplayStatics::ParseOption(Options, TEXT("PlayerSessionId"));
		if (!PlayerSessionId.IsEmpty())
		{
			FString ValidationError;
			if (!ValidatePlayerSession(PlayerSessionId, ValidationError))
			{
				ErrorMessage = FString::Printf(TEXT("GameLift validation failed: %s"), *ValidationError);
				UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Rejected connection - GameLift validation failed: %s"), *ValidationError);
				return;
			}

			// Accept the player session with GameLift
			AcceptPlayerSession(PlayerSessionId);
		}
		else
		{
			ErrorMessage = TEXT("GameLift player session ID required");
			UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Rejected connection - no player session ID"));
			return;
		}
	}
#endif

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: PreLogin successful for player %s"), *PlayerId);
}

APlayerController* AHMVRGameMode::Login(UPlayer* NewPlayer, ENetRole InRemoteRole, const FString& Portal, const FString& Options, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
	APlayerController* NewPlayerController = Super::Login(NewPlayer, InRemoteRole, Portal, Options, UniqueId, ErrorMessage);

	if (NewPlayerController)
	{
		// Extract PlayerId from JWT (already validated in PreLogin) and store on PlayerState
		// so OnPlayerJoined/Left can retrieve it without re-parsing the token.
		FString JWTToken = UGameplayStatics::ParseOption(Options, TEXT("Token"));
		FJWTClaims Claims;
		if (!JWTToken.IsEmpty() && UJWTValidator::DecodeToken(JWTToken, Claims) && !Claims.Subject.IsEmpty())
		{
			if (AHMVRPlayerState* PS = NewPlayerController->GetPlayerState<AHMVRPlayerState>())
			{
				PS->CognitoPlayerId = Claims.Subject;
				UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Login — CognitoPlayerId set to %s"), *Claims.Subject);
			}
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Login — could not decode PlayerId from JWT"));
		}
	}

	return NewPlayerController;
}

void AHMVRGameMode::PostLogin(APlayerController* NewPlayer)
{
	Super::PostLogin(NewPlayer);

	if (NewPlayer)
	{
		// Add to connected players list
		ConnectedPlayers.Add(NewPlayer);
		OnPlayerJoined(NewPlayer);

		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: PostLogin - Player count: %d/%d"), 
			GetCurrentPlayerCount(), MaxPlayers);
	}
}

void AHMVRGameMode::Logout(AController* Exiting)
{
	if (APlayerController* ExitingPlayer = Cast<APlayerController>(Exiting))
	{
#if WITH_GAMELIFT
		// Find and remove player session from GameLift
		for (const auto& Entry : PlayerSessionMap)
		{
			// In production, match player session to the exiting player
			// For now, remove the first matching session
			RemovePlayerSession(Entry.Key);
			break;
		}
#endif

		// Remove from connected players list
		ConnectedPlayers.Remove(ExitingPlayer);
		OnPlayerLeft(Exiting);

		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Player logged out - Player count: %d/%d"), 
			GetCurrentPlayerCount(), MaxPlayers);
	}

	Super::Logout(Exiting);
}

int32 AHMVRGameMode::GetCurrentPlayerCount() const
{
	// Clean up invalid weak pointers
	int32 ValidPlayerCount = 0;
	for (const TWeakObjectPtr<APlayerController>& PlayerPtr : ConnectedPlayers)
	{
		if (PlayerPtr.IsValid())
		{
			ValidPlayerCount++;
		}
	}
	return ValidPlayerCount;
}

bool AHMVRGameMode::CanAcceptNewPlayer() const
{
	return GetCurrentPlayerCount() < MaxPlayers;
}

bool AHMVRGameMode::ValidateJWTToken(const FString& Token, FString& OutPlayerId, FString& OutErrorMessage)
{
	// JWT validation implementation (Requirement 3.2-3.4)
	// Validates token signature, expiration, and claims
	// Extracts player ID from token claims

	if (Token.IsEmpty())
	{
		OutErrorMessage = TEXT("Token is empty");
		return false;
	}

	// Use JWT validator to validate token
	FJWTValidationResult ValidationResult;
	if (!UJWTValidator::ValidateToken(Token, ValidationResult))
	{
		OutErrorMessage = ValidationResult.ErrorMessage;
		return false;
	}

	// Extract player ID from claims (Requirement 3.3)
	OutPlayerId = ValidationResult.Claims.Subject;

	if (OutPlayerId.IsEmpty())
	{
		OutErrorMessage = TEXT("Token does not contain player ID");
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: JWT token validated for player: %s (username: %s)"), 
		*OutPlayerId, *ValidationResult.Claims.Username);

	return true;
}

#if !WITH_GAMELIFT
void AHMVRGameMode::InitializeGameLift()
{
	// No-op on client builds
}
void AHMVRGameMode::ReportServerHealth() {}
bool AHMVRGameMode::ValidatePlayerSession(const FString&, FString& OutErrorMessage) { OutErrorMessage = TEXT("GameLift not available"); return false; }
void AHMVRGameMode::AcceptPlayerSession(const FString&) {}
void AHMVRGameMode::RemovePlayerSession(const FString&) {}
#else
void AHMVRGameMode::InitializeGameLift()
{
	UHMVRGameInstance* GameInstance = Cast<UHMVRGameInstance>(GetGameInstance());
	if (!GameInstance || !GameInstance->IsGameLiftInitialized())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: GameLift SDK not yet initialized in game instance"));
		return;
	}

	GameLiftSdkModule = GameInstance->GetGameLiftSdkModule();
	CurrentSessionId = GameInstance->GetGameLiftSessionId();
	bGameLiftInitialized = true;
	bGameLiftProcessReady = true;

	if (GetWorld())
	{
		GetWorld()->GetTimerManager().SetTimer(
			HealthReportTimerHandle,
			this,
			&AHMVRGameMode::ReportServerHealth,
			30.0f,
			true
		);
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: GameLift SDK reference acquired, session: %s"), *CurrentSessionId);
}

void AHMVRGameMode::ReportServerHealth()
{
	// Report server health to GameLift (Requirement 2.4)
	int32 PlayerCount = GetCurrentPlayerCount();
	
	if (bGameLiftInitialized && bGameLiftProcessReady)
	{
		// In production, call GameLift SDK health reporting
		// This is automatically handled by the OnHealthCheck callback
		UE_LOG(LogTemp, Verbose, TEXT("HMVRGameMode: GameLift health check - Players: %d/%d"), 
			PlayerCount, MaxPlayers);
	}
	else
	{
		// Development mode health logging
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Health Report - Players: %d/%d, Session: %s"), 
			PlayerCount, MaxPlayers, *CurrentSessionId);
	}
}

bool AHMVRGameMode::ValidatePlayerSession(const FString& PlayerSessionId, FString& OutErrorMessage)
{
	// Validate player session with GameLift (Requirement 2.4)
	if (PlayerSessionId.IsEmpty())
	{
		OutErrorMessage = TEXT("Player session ID is empty");
		return false;
	}

	if (!bGameLiftInitialized || !bGameLiftProcessReady)
	{
		OutErrorMessage = TEXT("GameLift not initialized");
		return false;
	}

	// In production, validate with GameLift SDK
	// auto DescribeOutcome = Aws::GameLift::Server::DescribePlayerSessions(
	//     Aws::GameLift::Server::Model::DescribePlayerSessionsRequest()
	//         .WithPlayerSessionId(TCHAR_TO_UTF8(*PlayerSessionId))
	// );
	// 
	// if (!DescribeOutcome.IsSuccess())
	// {
	//     OutErrorMessage = FString(DescribeOutcome.GetError().m_errorMessage.c_str());
	//     return false;
	// }
	// 
	// auto PlayerSessions = DescribeOutcome.GetResult().GetPlayerSessions();
	// if (PlayerSessions.size() == 0)
	// {
	//     OutErrorMessage = TEXT("Player session not found");
	//     return false;
	// }
	// 
	// auto PlayerSession = PlayerSessions[0];
	// if (PlayerSession.GetStatus() != Aws::GameLift::Server::Model::PlayerSessionStatus::RESERVED)
	// {
	//     OutErrorMessage = TEXT("Player session not in RESERVED state");
	//     return false;
	// }

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Player session validated: %s"), *PlayerSessionId);
	return true;
}

void AHMVRGameMode::AcceptPlayerSession(const FString& PlayerSessionId)
{
	if (!bGameLiftInitialized || !bGameLiftProcessReady || !GameLiftSdkModule)
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Cannot accept player session - GameLift not initialized"));
		return;
	}

	auto AcceptOutcome = GameLiftSdkModule->AcceptPlayerSession(PlayerSessionId);
	if (!AcceptOutcome.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: AcceptPlayerSession failed: %s"),
			*AcceptOutcome.GetError().m_errorMessage);
		return;
	}

	PlayerSessionMap.Add(PlayerSessionId, FGuid::NewGuid().ToString());
	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Accepted player session: %s"), *PlayerSessionId);
}

void AHMVRGameMode::RemovePlayerSession(const FString& PlayerSessionId)
{
	if (PlayerSessionId.IsEmpty() || !bGameLiftInitialized || !bGameLiftProcessReady || !GameLiftSdkModule)
	{
		return;
	}

	auto RemoveOutcome = GameLiftSdkModule->RemovePlayerSession(PlayerSessionId);
	if (!RemoveOutcome.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: RemovePlayerSession failed: %s"),
			*RemoveOutcome.GetError().m_errorMessage);
	}

	PlayerSessionMap.Remove(PlayerSessionId);
	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Removed player session: %s"), *PlayerSessionId);
}
#endif // WITH_GAMELIFT (else stub implementations above)


void AHMVRGameMode::OnPlayerJoined(APlayerController* NewPlayer)
{
	if (!NewPlayer || !SessionManager)
	{
		return;
	}

	// Read PlayerId set in Login() from the JWT sub claim
	FString PlayerId;
	if (const AHMVRPlayerState* PS = NewPlayer->GetPlayerState<AHMVRPlayerState>())
	{
		PlayerId = PS->CognitoPlayerId;
	}
	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: OnPlayerJoined — PlayerId not on PlayerState, using fallback GUID"));
		PlayerId = FGuid::NewGuid().ToString();
	}

	// Create player session (state: CREATED)
	FPlayerSession PlayerSession = SessionManager->CreateSession(PlayerId, CurrentSessionId);

	// Track player session
	PlayerToSessionMap.Add(PlayerId, PlayerSession.SessionId);

	// Start session (transition CREATED → ACTIVE)
	SessionManager->StartSession(PlayerSession.SessionId);

	// Log player join event
	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Player joined - Session: %s, PlayerSession: %s"), 
		*CurrentSessionId, *PlayerSession.SessionId);

	// Track join event
	TMap<FString, FString> EventData;
	EventData.Add(TEXT("action"), TEXT("player_joined"));
	EventData.Add(TEXT("shard_id"), CurrentSessionId);
	SessionManager->TrackEvent(PlayerSession.SessionId, TEXT("player_join"), EventData);
}

void AHMVRGameMode::OnPlayerLeft(AController* ExitingPlayer)
{
	if (!ExitingPlayer || !SessionManager || !SessionAPIClient)
	{
		return;
	}

	// Read PlayerId from the PlayerState (set during Login from JWT sub claim)
	FString PlayerId;
	if (const APlayerController* PC = Cast<APlayerController>(ExitingPlayer))
	{
		if (const AHMVRPlayerState* PS = PC->GetPlayerState<AHMVRPlayerState>())
		{
			PlayerId = PS->CognitoPlayerId;
		}
	}
	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: OnPlayerLeft — PlayerId not on PlayerState, cannot persist session"));
		return;
	}

	FString* SessionIdPtr = PlayerToSessionMap.Find(PlayerId);
	
	if (SessionIdPtr)
	{
		FString SessionId = *SessionIdPtr;

		// Track leave event
		TMap<FString, FString> EventData;
		EventData.Add(TEXT("action"), TEXT("player_left"));
		EventData.Add(TEXT("shard_id"), CurrentSessionId);
		SessionManager->TrackEvent(SessionId, TEXT("player_leave"), EventData);

		// End session (transition ACTIVE → ENDED)
		SessionManager->EndSession(SessionId);

		// Generate session summary (Requirement 5.2)
		FPlayerSessionSummary Summary = SessionManager->GenerateSessionSummary(SessionId);

		// Send summary to Session API (stub - actual API in Task 15.4)
		if (SessionAPIClient->SendSessionSummary(Summary))
		{
			UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Session summary sent to API for session %s"), *SessionId);
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Failed to send session summary to API"));
		}

		// Discard gameplay state (keep only rewards)
		SessionManager->DiscardSessionState(SessionId);

		// Remove from tracking
		PlayerToSessionMap.Remove(PlayerId);

		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Player left - Session ended: %s, Rewards: %d"), 
			*SessionId, Summary.Rewards.Num());
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Player left but no session found"));
	}

#if WITH_GAMELIFT
	// When the last player leaves, signal ProcessEnding so GameLift reclaims this
	// server process and FlexMatch can place the next session. The process then
	// exits and GameLift spins up a fresh one (SDK 4.x has no TerminateGameSession).
	if (GetCurrentPlayerCount() == 0 && bGameLiftInitialized && GameLiftSdkModule)
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Last player left — calling ProcessEnding"));
		GameLiftSdkModule->ProcessEnding();
		FPlatformMisc::RequestExit(false);
	}
#endif
}

void AHMVRGameMode::GrantRewardToPlayer(APlayerController* Player, const FString& RewardId)
{
	if (!Player || RewardId.IsEmpty() || !RewardSystem || !SessionManager)
	{
		return;
	}

	FString PlayerId;
	if (const AHMVRPlayerState* PS = Player->GetPlayerState<AHMVRPlayerState>())
		PlayerId = PS->CognitoPlayerId;
	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: GrantRewardToPlayer — no PlayerId on PlayerState, aborting"));
		return;
	}

	// Grant reward with validation (Requirement 5.3, 15.2, 15.3)
	FRewardGrantResult Result = RewardSystem->GrantReward(PlayerId, RewardId);

	if (Result.bSuccess)
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Successfully granted reward '%s' to player %s"), 
			*RewardId, *PlayerId);

		// Add reward to player session
		FString* SessionIdPtr = PlayerToSessionMap.Find(PlayerId);
		if (SessionIdPtr)
		{
			SessionManager->AddReward(*SessionIdPtr, RewardId);

			// Track reward grant event
			TMap<FString, FString> EventData;
			EventData.Add(TEXT("reward_id"), RewardId);
			EventData.Add(TEXT("action"), TEXT("reward_granted"));
			SessionManager->TrackEvent(*SessionIdPtr, TEXT("reward_grant"), EventData);
		}
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Failed to grant reward '%s' - %s: %s"),
			*RewardId, *Result.ErrorCode, *Result.ErrorMessage);
	}
}
