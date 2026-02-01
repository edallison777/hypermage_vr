// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRGameMode.h"
#include "VRPawn.h"
#include "SessionManager.h"
#include "RewardSystem.h"
#include "SessionAPIClient.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "TimerManager.h"

// GameLift SDK includes would go here
// #include "GameLiftServerSDK.h"

AHMVRGameMode::AHMVRGameMode()
{
	// Set default pawn class
	DefaultPawnClass = AVRPawn::StaticClass();

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

void AHMVRGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Initializing game on map %s"), *MapName);

	// Initialize reward system
	if (RewardSystem && !RewardSystem->Initialize())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: Failed to initialize reward system"));
	}

	// Initialize GameLift if running on AWS
	if (GetWorld()->GetNetMode() == NM_DedicatedServer)
	{
		InitializeGameLift();
	}

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

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: PreLogin successful for player %s"), *PlayerId);
}

APlayerController* AHMVRGameMode::Login(UPlayer* NewPlayer, ENetRole InRemoteRole, const FString& Portal, const FString& Options, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
	APlayerController* NewPlayerController = Super::Login(NewPlayer, InRemoteRole, Portal, Options, UniqueId, ErrorMessage);

	if (NewPlayerController)
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Player logged in successfully"));
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
		// Find and remove player session from GameLift
		for (const auto& Entry : PlayerSessionMap)
		{
			// In production, match player session to the exiting player
			// For now, remove the first matching session
			RemovePlayerSession(Entry.Key);
			break;
		}

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

void AHMVRGameMode::InitializeGameLift()
{
	// GameLift SDK initialization (Requirement 2.4)
	// In production, this would:
	// 1. Initialize GameLift Server SDK
	// 2. Call ProcessReady() to signal server is ready
	// 3. Set up callbacks for player session validation
	// 4. Start health reporting

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Initializing GameLift SDK"));

	// Check if running in GameLift environment
	// In production, check for GameLift environment variables
	const bool bIsGameLiftEnvironment = false; // TODO: Check for GameLift env vars

	if (bIsGameLiftEnvironment)
	{
		// Initialize GameLift Server SDK
		// auto InitSDKOutcome = Aws::GameLift::Server::InitSDK();
		// if (!InitSDKOutcome.IsSuccess())
		// {
		//     UE_LOG(LogTemp, Error, TEXT("GameLift InitSDK failed: %s"), 
		//         *FString(InitSDKOutcome.GetError().GetErrorMessage().c_str()));
		//     return;
		// }

		// Set up process parameters
		// Aws::GameLift::Server::ProcessParameters ProcessParams;
		// ProcessParams.OnStartGameSession = [this](Aws::GameLift::Server::Model::GameSession GameSession)
		// {
		//     // Handle game session start
		//     CurrentSessionId = FString(GameSession.GetGameSessionId().c_str());
		//     UE_LOG(LogTemp, Log, TEXT("GameLift: Game session started: %s"), *CurrentSessionId);
		// };
		// 
		// ProcessParams.OnProcessTerminate = [this]()
		// {
		//     // Handle process termination
		//     UE_LOG(LogTemp, Log, TEXT("GameLift: Process terminating"));
		//     // Graceful shutdown
		// };
		// 
		// ProcessParams.OnHealthCheck = []() -> bool
		// {
		//     // Return server health status
		//     return true;
		// };
		// 
		// ProcessParams.port = 7777; // Game server port
		// 
		// // Call ProcessReady
		// auto ProcessReadyOutcome = Aws::GameLift::Server::ProcessReady(ProcessParams);
		// if (!ProcessReadyOutcome.IsSuccess())
		// {
		//     UE_LOG(LogTemp, Error, TEXT("GameLift ProcessReady failed: %s"),
		//         *FString(ProcessReadyOutcome.GetError().GetErrorMessage().c_str()));
		//     return;
		// }

		bGameLiftInitialized = true;
		bGameLiftProcessReady = true;
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: GameLift SDK initialized and ProcessReady called"));
	}
	else
	{
		// Mock initialization for development
		bGameLiftInitialized = false;
		UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Running in development mode (GameLift disabled)"));
	}

	// Start health reporting timer
	if (GetWorld())
	{
		GetWorld()->GetTimerManager().SetTimer(
			HealthReportTimerHandle,
			this,
			&AHMVRGameMode::ReportServerHealth,
			30.0f, // Report every 30 seconds
			true
		);
	}
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
	//     OutErrorMessage = FString(DescribeOutcome.GetError().GetErrorMessage().c_str());
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
	// Accept player session with GameLift (Requirement 2.4)
	if (!bGameLiftInitialized || !bGameLiftProcessReady)
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Cannot accept player session - GameLift not initialized"));
		return;
	}

	// In production, call GameLift SDK AcceptPlayerSession
	// auto AcceptOutcome = Aws::GameLift::Server::AcceptPlayerSession(TCHAR_TO_UTF8(*PlayerSessionId));
	// if (!AcceptOutcome.IsSuccess())
	// {
	//     UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: AcceptPlayerSession failed: %s"),
	//         *FString(AcceptOutcome.GetError().GetErrorMessage().c_str()));
	//     return;
	// }

	// Track the player session
	PlayerSessionMap.Add(PlayerSessionId, FGuid::NewGuid().ToString());

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Accepted player session: %s"), *PlayerSessionId);
}

void AHMVRGameMode::RemovePlayerSession(const FString& PlayerSessionId)
{
	// Remove player session from GameLift (Requirement 2.4)
	if (PlayerSessionId.IsEmpty())
	{
		return;
	}

	if (!bGameLiftInitialized || !bGameLiftProcessReady)
	{
		return;
	}

	// In production, call GameLift SDK RemovePlayerSession
	// auto RemoveOutcome = Aws::GameLift::Server::RemovePlayerSession(TCHAR_TO_UTF8(*PlayerSessionId));
	// if (!RemoveOutcome.IsSuccess())
	// {
	//     UE_LOG(LogTemp, Error, TEXT("HMVRGameMode: RemovePlayerSession failed: %s"),
	//         *FString(RemoveOutcome.GetError().GetErrorMessage().c_str()));
	// }

	// Remove from tracking
	PlayerSessionMap.Remove(PlayerSessionId);

	UE_LOG(LogTemp, Log, TEXT("HMVRGameMode: Removed player session: %s"), *PlayerSessionId);
}

void AHMVRGameMode::ProcessPlayerSessionValidation(const FString& PlayerSessionId)
{
	// Legacy method - replaced by ValidatePlayerSession and AcceptPlayerSession
	FString ErrorMessage;
	if (ValidatePlayerSession(PlayerSessionId, ErrorMessage))
	{
		AcceptPlayerSession(PlayerSessionId);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameMode: Player session validation failed: %s"), *ErrorMessage);
	}
}

void AHMVRGameMode::OnPlayerJoined(APlayerController* NewPlayer)
{
	if (!NewPlayer || !SessionManager)
	{
		return;
	}

	// Extract player ID from JWT token (already validated in PreLogin)
	FString PlayerId = FGuid::NewGuid().ToString(); // TODO: Extract from validated JWT

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

	// Find player session
	FString PlayerId = FGuid::NewGuid().ToString(); // TODO: Extract from player state
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
}

void AHMVRGameMode::GrantRewardToPlayer(APlayerController* Player, const FString& RewardId)
{
	if (!Player || RewardId.IsEmpty() || !RewardSystem || !SessionManager)
	{
		return;
	}

	// Extract player ID (TODO: from player state)
	FString PlayerId = FGuid::NewGuid().ToString();

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
