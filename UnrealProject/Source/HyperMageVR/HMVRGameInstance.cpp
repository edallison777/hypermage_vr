// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRGameInstance.h"
#include "JWTValidator.h"
#include "VoiceChatInterface.h"
#include "MockVoiceProvider.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "GameLiftServerSDK.h"

void UHMVRGameInstance::Init()
{
	Super::Init();

	if (IsRunningDedicatedServer())
	{
		InitializeGameLift();
	}

	// Initialize voice chat manager with mock provider
	VoiceChatManager = NewObject<UVoiceChatManager>(this);
	if (VoiceChatManager)
	{
		// Create mock voice provider for development/testing
		UMockVoiceProvider* MockProvider = NewObject<UMockVoiceProvider>(this);
		TScriptInterface<IVoiceChatProvider> ProviderInterface;
		ProviderInterface.SetObject(MockProvider);
		ProviderInterface.SetInterface(Cast<IVoiceChatProvider>(MockProvider));

		if (VoiceChatManager->Initialize(ProviderInterface))
		{
			UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Voice chat initialized with mock provider"));
		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Failed to initialize voice chat"));
		}
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Initialized"));
}

void UHMVRGameInstance::Shutdown()
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Shutting down"));

	// Shutdown voice chat
	if (VoiceChatManager)
	{
		VoiceChatManager->Shutdown();
		VoiceChatManager = nullptr;
	}

	Super::Shutdown();
}

void UHMVRGameInstance::InitializeGameLift()
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Initializing GameLift SDK"));

	GameLiftSdkModule = &FModuleManager::LoadModuleChecked<FGameLiftServerSDKModule>(FName("GameLiftServerSDK"));

	// SDK 5.x on AMAZON_LINUX_2 fleets (AuxProxy agent) requires explicit WebSocket URL.
	// AuxProxy listens on 127.0.0.1:5757 for SDK 5.x WebSocket connections.
	FServerParameters ServerParams;
	ServerParams.m_webSocketUrl = TEXT("wss://127.0.0.1:5757");

	auto InitSDKOutcome = GameLiftSdkModule->InitSDK(ServerParams);
	if (!InitSDKOutcome.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: GameLift InitSDK failed: %s"),
			*InitSDKOutcome.GetError().m_errorMessage);
		return;
	}

	FProcessParameters ProcessParams;

	ProcessParams.OnStartGameSession.BindLambda([this](Aws::GameLift::Server::Model::GameSession GameSession)
	{
		GameLiftSessionId = FString(GameSession.GetGameSessionId());
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: GameLift game session started: %s"), *GameLiftSessionId);
		GameLiftSdkModule->ActivateGameSession();
	});

	ProcessParams.OnUpdateGameSession.BindLambda([](Aws::GameLift::Server::Model::UpdateGameSession)
	{
		// Backfill not supported
	});

	ProcessParams.OnHealthCheck.BindLambda([]() { return true; });

	ProcessParams.OnTerminate.BindLambda([this]()
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: GameLift process terminating"));
		if (GameLiftSdkModule)
		{
			GameLiftSdkModule->ProcessEnding();
		}
		FGenericPlatformMisc::RequestExit(false);
	});

	ProcessParams.port = 7777;
	ProcessParams.logParameters.Add(TEXT("/local/game/logs/myserver.log"));

	auto ProcessReadyOutcome = GameLiftSdkModule->ProcessReady(ProcessParams);
	if (!ProcessReadyOutcome.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: GameLift ProcessReady failed: %s"),
			*ProcessReadyOutcome.GetError().m_errorMessage);
		return;
	}

	bGameLiftInitialized = true;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: GameLift SDK initialized and ProcessReady called"));
}

void UHMVRGameInstance::SetJWTToken(const FString& Token)
{
	JWTToken = Token;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: JWT token set"));

	// Decode token to extract PlayerId
	FJWTClaims Claims;
	if (UJWTValidator::DecodeToken(Token, Claims))
	{
		PlayerId = Claims.Subject;
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Player ID extracted from token: %s"), *PlayerId);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: Failed to decode JWT token"));
	}
}

void UHMVRGameInstance::SetPlayerSessionId(const FString& SessionId)
{
	PlayerSessionId = SessionId;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Player session ID set: %s"), *SessionId);
}

void UHMVRGameInstance::StartMatchmaking()
{
	if (JWTToken.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Cannot start matchmaking - no JWT token"));
		OnMatchmakingFailure(TEXT("No authentication token"));
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Starting matchmaking"));

	// TODO: Call Session API to start matchmaking
	// POST /matchmaking/start with JWT token
	// Store matchmaking ticket ID
	// Poll for matchmaking status

	// Mock matchmaking for development
	MatchmakingTicketId = FGuid::NewGuid().ToString();
	
	// Simulate matchmaking success after delay
	FTimerHandle MatchmakingTimerHandle;
	GetWorld()->GetTimerManager().SetTimer(MatchmakingTimerHandle, [this]()
	{
		// Mock server connection details
		OnMatchmakingSuccess(TEXT("127.0.0.1"), 7777, FGuid::NewGuid().ToString());
	}, 3.0f, false);
}

void UHMVRGameInstance::CancelMatchmaking()
{
	if (MatchmakingTicketId.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: No active matchmaking to cancel"));
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Cancelling matchmaking: %s"), *MatchmakingTicketId);

	// TODO: Call Session API to cancel matchmaking
	// DELETE /matchmaking/{ticketId}

	MatchmakingTicketId.Empty();
}

void UHMVRGameInstance::ConnectToGameServer(const FString& ServerAddress, int32 Port)
{
	if (JWTToken.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Cannot connect - no JWT token"));
		OnConnectionFailure(TEXT("No authentication token"));
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Connecting to %s:%d"), *ServerAddress, Port);

	// Build connection URL with JWT token and player session ID
	FString TravelURL = FString::Printf(TEXT("%s:%d?Token=%s"), *ServerAddress, Port, *JWTToken);
	
	if (!PlayerSessionId.IsEmpty())
	{
		TravelURL += FString::Printf(TEXT("?PlayerSessionId=%s"), *PlayerSessionId);
	}

	// Connect to server
	UGameplayStatics::OpenLevel(this, FName(*TravelURL), true);
}

void UHMVRGameInstance::OnMatchmakingSuccess(const FString& ServerAddress, int32 Port, const FString& SessionId)
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Matchmaking successful - Server: %s:%d, Session: %s"), 
		*ServerAddress, Port, *SessionId);

	SetPlayerSessionId(SessionId);
	ConnectToGameServer(ServerAddress, Port);
}

void UHMVRGameInstance::OnMatchmakingFailure(const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Matchmaking failed - %s"), *ErrorMessage);

	MatchmakingTicketId.Empty();

	// TODO: Notify UI of matchmaking failure
}

void UHMVRGameInstance::OnConnectionSuccess()
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Connected to game server successfully"));

	// TODO: Notify UI of successful connection
}

void UHMVRGameInstance::OnConnectionFailure(const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Connection failed - %s"), *ErrorMessage);

	// TODO: Notify UI of connection failure
	// TODO: Return to main menu
}
