// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRGameInstance.h"
#include "JWTValidator.h"
#include "VoiceChatInterface.h"
#include "MockVoiceProvider.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "GameLiftServerSDK.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

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

	auto InitSDKOutcome = GameLiftSdkModule->InitSDK();
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

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Starting matchmaking via Session API"));

	if (UHMVRStatusWidget* Widget = EnsureStatusWidget())
	{
		Widget->ShowSearching();
	}
	OnMatchmakingStatusChanged.Broadcast(TEXT("SEARCHING"));

	FString RequestPlayerId = PlayerId.IsEmpty() ? FGuid::NewGuid().ToString() : PlayerId;

	TSharedRef<FJsonObject> RequestBody = MakeShared<FJsonObject>();
	RequestBody->SetStringField(TEXT("playerId"), RequestPlayerId);

	TSharedRef<FJsonObject> Attributes = MakeShared<FJsonObject>();
	Attributes->SetNumberField(TEXT("skill"), 10.0);
	Attributes->SetStringField(TEXT("region"), TEXT("eu-west-1"));
	RequestBody->SetObjectField(TEXT("playerAttributes"), Attributes);

	FString BodyString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&BodyString);
	FJsonSerializer::Serialize(RequestBody, Writer);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(SessionApiBaseUrl + TEXT("/matchmaking/start"));
	HttpRequest->SetVerb(TEXT("POST"));
	HttpRequest->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	HttpRequest->SetHeader(TEXT("Authorization"), JWTToken);
	HttpRequest->SetContentAsString(BodyString);
	HttpRequest->OnProcessRequestComplete().BindUObject(this, &UHMVRGameInstance::OnStartMatchmakingResponse);
	HttpRequest->ProcessRequest();
}

void UHMVRGameInstance::OnStartMatchmakingResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	if (!bConnectedSuccessfully || !Response.IsValid())
	{
		OnMatchmakingFailure(TEXT("No internet connection — check your network and try again"));
		return;
	}

	if (Response->GetResponseCode() != 200)
	{
		OnMatchmakingFailure(FString::Printf(TEXT("Matchmaking start failed: HTTP %d — %s"),
			Response->GetResponseCode(), *Response->GetContentAsString()));
		return;
	}

	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		OnMatchmakingFailure(TEXT("Failed to parse matchmaking start response"));
		return;
	}

	MatchmakingTicketId = JsonObject->GetStringField(TEXT("ticketId"));
	MatchmakingPollAttempt = 0;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Matchmaking started, ticket: %s"), *MatchmakingTicketId);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(
			MatchmakingPollTimerHandle,
			this,
			&UHMVRGameInstance::PollMatchmakingStatus,
			3.0f,
			true,
			3.0f
		);
	}
}

void UHMVRGameInstance::PollMatchmakingStatus()
{
	if (MatchmakingTicketId.IsEmpty())
	{
		return;
	}

	if (MatchmakingPollAttempt >= MaxMatchmakingPollAttempts)
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(MatchmakingPollTimerHandle);
		}
		OnMatchmakingFailure(TEXT("Matchmaking timed out after 2 minutes"));
		return;
	}

	++MatchmakingPollAttempt;

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(FString::Printf(TEXT("%s/matchmaking/status/%s"), *SessionApiBaseUrl, *MatchmakingTicketId));
	HttpRequest->SetVerb(TEXT("GET"));
	HttpRequest->SetHeader(TEXT("Authorization"), JWTToken);
	HttpRequest->OnProcessRequestComplete().BindUObject(this, &UHMVRGameInstance::OnMatchmakingStatusResponse);
	HttpRequest->ProcessRequest();
}

void UHMVRGameInstance::OnMatchmakingStatusResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	// Non-200 responses are non-fatal — keep polling on next timer tick
	if (!bConnectedSuccessfully || !Response.IsValid() || Response->GetResponseCode() != 200)
	{
		return;
	}

	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return;
	}

	FString Status = JsonObject->GetStringField(TEXT("status"));
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Matchmaking status: %s (attempt %d/%d)"),
		*Status, MatchmakingPollAttempt, MaxMatchmakingPollAttempts);

	if (Status == TEXT("COMPLETED"))
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(MatchmakingPollTimerHandle);
		}

		const TSharedPtr<FJsonObject>* ConnectionInfoObj;
		if (!JsonObject->TryGetObjectField(TEXT("gameSessionConnectionInfo"), ConnectionInfoObj))
		{
			OnMatchmakingFailure(TEXT("COMPLETED but no gameSessionConnectionInfo in response"));
			return;
		}

		FString ServerAddress;
		double PortDouble = 7777.0;
		(*ConnectionInfoObj)->TryGetStringField(TEXT("ipAddress"), ServerAddress);
		(*ConnectionInfoObj)->TryGetNumberField(TEXT("port"), PortDouble);
		int32 Port = static_cast<int32>(PortDouble);

		const TArray<TSharedPtr<FJsonValue>>* PlayerSessionsArray;
		if ((*ConnectionInfoObj)->TryGetArrayField(TEXT("matchedPlayerSessions"), PlayerSessionsArray)
			&& PlayerSessionsArray->Num() > 0)
		{
			const TSharedPtr<FJsonObject>* FirstSession;
			if ((*PlayerSessionsArray)[0]->TryGetObject(FirstSession))
			{
				FString NewPlayerSessionId;
				(*FirstSession)->TryGetStringField(TEXT("playerSessionId"), NewPlayerSessionId);
				if (!NewPlayerSessionId.IsEmpty())
				{
					SetPlayerSessionId(NewPlayerSessionId);
				}
			}
		}

		OnMatchmakingSuccess(ServerAddress, Port, PlayerSessionId);
	}
	else if (Status == TEXT("FAILED") || Status == TEXT("TIMED_OUT") || Status == TEXT("CANCELLED"))
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(MatchmakingPollTimerHandle);
		}
		FString Reason;
		JsonObject->TryGetStringField(TEXT("statusReason"), Reason);
		OnMatchmakingFailure(FString::Printf(TEXT("Matchmaking %s: %s"), *Status, *Reason));
	}
	// SEARCHING / PLACING / REQUIRES_ACCEPTANCE — keep polling via timer
}

void UHMVRGameInstance::CancelMatchmaking()
{
	if (MatchmakingTicketId.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: No active matchmaking to cancel"));
		return;
	}

	// Stop polling before sending cancel so we don't act on stale status responses
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(MatchmakingPollTimerHandle);
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Cancelling matchmaking: %s"), *MatchmakingTicketId);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(FString::Printf(TEXT("%s/matchmaking/cancel/%s"), *SessionApiBaseUrl, *MatchmakingTicketId));
	HttpRequest->SetVerb(TEXT("DELETE"));
	HttpRequest->SetHeader(TEXT("Authorization"), JWTToken);
	HttpRequest->OnProcessRequestComplete().BindUObject(this, &UHMVRGameInstance::OnCancelMatchmakingResponse);
	HttpRequest->ProcessRequest();

	MatchmakingTicketId.Empty();

	OnMatchmakingStatusChanged.Broadcast(TEXT("CANCELLED"));
	if (ActiveStatusWidget && IsValid(ActiveStatusWidget))
	{
		ActiveStatusWidget->HideWidget();
	}
}

void UHMVRGameInstance::OnCancelMatchmakingResponse(FHttpRequestPtr /*Request*/, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	if (!bConnectedSuccessfully || !Response.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: Cancel matchmaking — network error (non-fatal)"));
		return;
	}
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Cancel matchmaking — HTTP %d"), Response->GetResponseCode());
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

	FString TravelURL = FString::Printf(TEXT("%s:%d?Token=%s"), *ServerAddress, Port, *JWTToken);
	if (!PlayerSessionId.IsEmpty())
	{
		TravelURL += FString::Printf(TEXT("&PlayerSessionId=%s"), *PlayerSessionId);
	}

	UGameplayStatics::OpenLevel(this, FName(*TravelURL), true);
}

void UHMVRGameInstance::ReturnToMainMenu()
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Returning to main menu: %s"), *MainMenuLevelName.ToString());
	UGameplayStatics::OpenLevel(this, MainMenuLevelName, true);
}

void UHMVRGameInstance::OnMatchmakingSuccess(const FString& ServerAddress, int32 Port, const FString& SessionId)
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Matchmaking successful - Server: %s:%d, Session: %s"),
		*ServerAddress, Port, *SessionId);

	OnMatchmakingStatusChanged.Broadcast(TEXT("COMPLETED"));

	if (UHMVRStatusWidget* Widget = EnsureStatusWidget())
	{
		Widget->ShowConnecting();
	}

	SetPlayerSessionId(SessionId);
	ConnectToGameServer(ServerAddress, Port);
}

void UHMVRGameInstance::OnMatchmakingFailure(const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Matchmaking failed - %s"), *ErrorMessage);

	MatchmakingTicketId.Empty();

	OnMatchmakingError.Broadcast(ErrorMessage);

	if (UHMVRStatusWidget* Widget = EnsureStatusWidget())
	{
		Widget->ShowError(ErrorMessage);
	}
}

void UHMVRGameInstance::OnConnectionSuccess()
{
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Connected to game server successfully"));

	OnConnectionEstablished.Broadcast();

	if (ActiveStatusWidget && IsValid(ActiveStatusWidget))
	{
		ActiveStatusWidget->ShowSuccess();
	}
}

void UHMVRGameInstance::OnConnectionFailure(const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Error, TEXT("HMVRGameInstance: Connection failed - %s"), *ErrorMessage);

	OnConnectionError.Broadcast(ErrorMessage);

	if (UHMVRStatusWidget* Widget = EnsureStatusWidget())
	{
		Widget->ShowError(FString::Printf(TEXT("Connection failed: %s"), *ErrorMessage));
	}

	ReturnToMainMenu();
}

UHMVRStatusWidget* UHMVRGameInstance::EnsureStatusWidget()
{
	if (ActiveStatusWidget && IsValid(ActiveStatusWidget))
	{
		return ActiveStatusWidget;
	}

	if (!StatusWidgetClass)
	{
		UE_LOG(LogTemp, Verbose, TEXT("HMVRGameInstance: StatusWidgetClass not set — no UI shown"));
		return nullptr;
	}

	APlayerController* PC = GetFirstLocalPlayerController(GetWorld());
	if (!PC)
	{
		return nullptr;
	}

	ActiveStatusWidget = CreateWidget<UHMVRStatusWidget>(PC, StatusWidgetClass);
	if (ActiveStatusWidget)
	{
		ActiveStatusWidget->AddToViewport();
		ActiveStatusWidget->OnRetryRequested.AddDynamic(this, &UHMVRGameInstance::StartMatchmaking);
		ActiveStatusWidget->OnCancelRequested.AddDynamic(this, &UHMVRGameInstance::CancelMatchmaking);
	}

	return ActiveStatusWidget;
}
