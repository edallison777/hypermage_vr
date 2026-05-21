// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRGameInstance.h"
#include "HMVRLoginWidget.h"
#include "HMVRSaveGame.h"
#include "JWTValidator.h"
#include "VoiceChatInterface.h"
#include "MockVoiceProvider.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#if WITH_GAMELIFT
#include "GameLiftServerSDK.h"
#endif
#include "Components/StereoLayerComponent.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Slate/WidgetRenderer.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

const FString UHMVRGameInstance::CredentialsSaveSlot = TEXT("HyperMageVR_Credentials");

void UHMVRGameInstance::Init()
{
	Super::Init();

	if (IsRunningDedicatedServer())
	{
#if WITH_GAMELIFT
		InitializeGameLift();
#endif
		return;
	}

	TryAutoLogin();

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

void UHMVRGameInstance::OnStart()
{
	Super::OnStart();
	bOnStartFired = true;

	if (bAutoLoginAttempted)
	{
		HandleAutoLoginResult(bAutoLoginSucceeded, AutoLoginError);
	}
	// else: still waiting for HTTP — HandleAutoLoginResult called from OnTokenRefreshResponse
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
#if !WITH_GAMELIFT
	// No-op on client builds — GameLift SDK is server-only
}
#else
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
#endif // WITH_GAMELIFT

// ── Auto-login (refresh token persistence) ────────────────────────────────────

void UHMVRGameInstance::TryAutoLogin()
{
	UHMVRSaveGame* Save = Cast<UHMVRSaveGame>(
		UGameplayStatics::LoadGameFromSlot(CredentialsSaveSlot, 0));

	if (!Save || Save->RefreshToken.IsEmpty())
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: No saved credentials — showing login UI"));
		bAutoLoginAttempted = true;
		bAutoLoginSucceeded = false;
		OnAutoLoginComplete.Broadcast(false, TEXT(""));
		return;
	}

	CachedUsername = Save->CachedUsername;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Saved credentials found for '%s' — refreshing token"),
		*CachedUsername);

	// POST to Cognito REFRESH_TOKEN_AUTH
	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("AuthFlow"), TEXT("REFRESH_TOKEN_AUTH"));
	Body->SetStringField(TEXT("ClientId"), TEXT("2iinqhoja78kj1et6rcv28bjvf"));

	TSharedRef<FJsonObject> Params = MakeShared<FJsonObject>();
	Params->SetStringField(TEXT("REFRESH_TOKEN"), Save->RefreshToken);
	Body->SetObjectField(TEXT("AuthParameters"), Params);

	FString BodyString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&BodyString);
	FJsonSerializer::Serialize(Body, Writer);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(TEXT("https://cognito-idp.eu-west-1.amazonaws.com/"));
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/x-amz-json-1.1"));
	Req->SetHeader(TEXT("X-Amz-Target"), TEXT("AWSCognitoIdentityProviderService.InitiateAuth"));
	Req->SetContentAsString(BodyString);
	Req->OnProcessRequestComplete().BindUObject(this, &UHMVRGameInstance::OnTokenRefreshResponse);
	Req->ProcessRequest();
}

void UHMVRGameInstance::OnTokenRefreshResponse(FHttpRequestPtr /*Request*/, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	auto Finish = [this](bool bSuccess, const FString& Error)
	{
		bAutoLoginAttempted = true;
		bAutoLoginSucceeded = bSuccess;
		AutoLoginError = Error;
		OnAutoLoginComplete.Broadcast(bSuccess, Error);
		if (bOnStartFired)
		{
			HandleAutoLoginResult(bSuccess, Error);
		}
	};

	if (!bConnectedSuccessfully || !Response.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: Auto-login — network error, showing login UI"));
		Finish(false, TEXT("No internet connection"));
		return;
	}

	TSharedPtr<FJsonObject> Json;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());

	if (Response->GetResponseCode() != 200 || !FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Refresh token invalid (HTTP %d) — clearing credentials"),
			Response->GetResponseCode());
		ClearSavedCredentials();
		Finish(false, TEXT("Session expired — please log in again"));
		return;
	}

	const TSharedPtr<FJsonObject>* AuthResult;
	if (!Json->TryGetObjectField(TEXT("AuthenticationResult"), AuthResult))
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRGameInstance: Auto-login — unexpected Cognito response"));
		ClearSavedCredentials();
		Finish(false, TEXT("Unexpected authentication response"));
		return;
	}

	FString IdToken;
	(*AuthResult)->TryGetStringField(TEXT("IdToken"), IdToken);

	if (IdToken.IsEmpty())
	{
		ClearSavedCredentials();
		Finish(false, TEXT("Empty token in response"));
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Auto-login succeeded for '%s'"), *CachedUsername);
	SetJWTToken(IdToken);
	Finish(true, TEXT(""));
}

void UHMVRGameInstance::SetRefreshToken(const FString& Token, const FString& Username)
{
	if (Token.IsEmpty())
	{
		return;
	}
	SaveCredentials(Token, Username);
}

void UHMVRGameInstance::SaveCredentials(const FString& RefreshToken, const FString& Username)
{
	UHMVRSaveGame* Save = Cast<UHMVRSaveGame>(
		UGameplayStatics::CreateSaveGameObject(UHMVRSaveGame::StaticClass()));
	Save->RefreshToken = RefreshToken;
	Save->CachedUsername = Username;
	Save->SavedAt = FDateTime::UtcNow().ToUnixTimestamp();
	UGameplayStatics::SaveGameToSlot(Save, CredentialsSaveSlot, 0);
	CachedUsername = Username;
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Credentials saved for '%s'"), *Username);
}

void UHMVRGameInstance::ClearSavedCredentials()
{
	UGameplayStatics::DeleteGameInSlot(CredentialsSaveSlot, 0);
	CachedUsername.Empty();
	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Saved credentials cleared"));
}

void UHMVRGameInstance::Login(const FString& Username, const FString& Password)
{
	PendingLoginUsername = Username;

	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("AuthFlow"), TEXT("USER_PASSWORD_AUTH"));
	Body->SetStringField(TEXT("ClientId"), TEXT("2iinqhoja78kj1et6rcv28bjvf"));

	TSharedRef<FJsonObject> Params = MakeShared<FJsonObject>();
	Params->SetStringField(TEXT("USERNAME"), Username);
	Params->SetStringField(TEXT("PASSWORD"), Password);
	Body->SetObjectField(TEXT("AuthParameters"), Params);

	FString BodyString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&BodyString);
	FJsonSerializer::Serialize(Body, Writer);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(TEXT("https://cognito-idp.eu-west-1.amazonaws.com/"));
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/x-amz-json-1.1"));
	Req->SetHeader(TEXT("X-Amz-Target"), TEXT("AWSCognitoIdentityProviderService.InitiateAuth"));
	Req->SetContentAsString(BodyString);
	Req->OnProcessRequestComplete().BindUObject(this, &UHMVRGameInstance::OnLoginResponse);
	Req->ProcessRequest();

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Login attempt for '%s'"), *Username);
}

void UHMVRGameInstance::OnLoginResponse(FHttpRequestPtr /*Request*/, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	if (!bConnectedSuccessfully || !Response.IsValid())
	{
		OnLoginResult.Broadcast(false, TEXT("Network error — check your connection"));
		return;
	}

	if (Response->GetResponseCode() != 200)
	{
		TSharedPtr<FJsonObject> Json;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
		FString ErrorMessage = FString::Printf(TEXT("Login failed (HTTP %d)"), Response->GetResponseCode());
		if (FJsonSerializer::Deserialize(Reader, Json) && Json.IsValid())
		{
			FString Msg;
			if (Json->TryGetStringField(TEXT("message"), Msg) && !Msg.IsEmpty())
			{
				ErrorMessage = Msg;
			}
		}
		OnLoginResult.Broadcast(false, ErrorMessage);
		return;
	}

	TSharedPtr<FJsonObject> Json;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
	{
		OnLoginResult.Broadcast(false, TEXT("Unexpected server response"));
		return;
	}

	const TSharedPtr<FJsonObject>* AuthResult;
	if (!Json->TryGetObjectField(TEXT("AuthenticationResult"), AuthResult))
	{
		OnLoginResult.Broadcast(false, TEXT("Unexpected authentication response"));
		return;
	}

	FString IdToken, RefreshToken;
	(*AuthResult)->TryGetStringField(TEXT("IdToken"), IdToken);
	(*AuthResult)->TryGetStringField(TEXT("RefreshToken"), RefreshToken);

	if (IdToken.IsEmpty())
	{
		OnLoginResult.Broadcast(false, TEXT("Empty token in response"));
		return;
	}

	SetJWTToken(IdToken);
	if (!RefreshToken.IsEmpty())
	{
		SaveCredentials(RefreshToken, PendingLoginUsername);
	}

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Login successful for '%s'"), *PendingLoginUsername);
	OnLoginResult.Broadcast(true, TEXT(""));
	TearDownLoginWidget();
	StartMatchmaking();
}

void UHMVRGameInstance::HandleAutoLoginResult(bool bSuccess, const FString& /*ErrorMessage*/)
{
	if (bSuccess)
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Auto-login succeeded — starting matchmaking"));
		StartMatchmaking();
	}
	else
	{
		UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Auto-login failed — showing login UI"));
		// Delay 2s so the OpenXR runtime has delivered at least one HMD pose before we position the widget
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().SetTimer(
				ShowLoginWidgetRetryHandle,
				this,
				&UHMVRGameInstance::ShowLoginWidget,
				2.0f,
				false
			);
		}
	}
}

void UHMVRGameInstance::ShowLoginWidget()
{
	APlayerController* PC = GetFirstLocalPlayerController(GetWorld());
	if (!PC)
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().SetTimer(
				ShowLoginWidgetRetryHandle,
				this,
				&UHMVRGameInstance::ShowLoginWidget,
				0.5f,
				false
			);
		}
		return;
	}

	UWorld* World = GetWorld();
	if (!World) return;

	World->GetTimerManager().ClearTimer(ShowLoginWidgetRetryHandle);

	// Render target — the widget is drawn into this each frame.
	// ClearColor set to the panel background blue so the stereo layer shows something
	// even if DrawWidget clears to transparent before the widget renders.
	LoginWidgetRT = NewObject<UTextureRenderTarget2D>(this);
	LoginWidgetRT->bAutoGenerateMips = false;
	LoginWidgetRT->RenderTargetFormat = RTF_RGBA8;
	LoginWidgetRT->ClearColor = FLinearColor(0.1f, 0.2f, 0.6f, 1.0f);
	LoginWidgetRT->InitAutoFormat(1024, 768);
	LoginWidgetRT->UpdateResourceImmediate(true);

	// Create the UMG widget — AddToViewport so it stays in the input stack
	// (invisible in the VR headset, but receives focus/keyboard events)
	LoginWidgetInstance = CreateWidget<UHMVRLoginWidget>(PC, UHMVRLoginWidget::StaticClass());
	if (LoginWidgetInstance)
	{
		LoginWidgetInstance->AddToViewport(-100);
	}

	// Stereo compositor overlay quad — submitted directly to the Quest runtime,
	// displayed correctly in both eyes without going through the 3D render pipeline.
	// Spawn at origin then SetRelativeLocation on the component directly — this is
	// the same pattern confirmed working in the May-19 session (triggers MarkStereoLayerDirty).
	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* LayerActor = World->SpawnActor<AActor>(
		AActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
	if (LayerActor)
	{
		UStereoLayerComponent* StereoComp =
			NewObject<UStereoLayerComponent>(LayerActor, TEXT("LoginStereoLayer"));
		StereoComp->SetTexture(LoginWidgetRT);
		StereoComp->SetQuadSize(FVector2D(80.f, 60.f)); // 80 x 60 cm panel
		// StereoLayerType stays SLT_FaceLocked (constructor default) — confirmed visible.
		// bLiveTexture=false: compositor copies the RT into its own swapchain buffer, avoiding
		// a race between DrawWidget writing and the compositor reading the same texture.
		StereoComp->bLiveTexture = false;
		StereoComp->SetPriority(1);
		LayerActor->SetRootComponent(StereoComp);
		StereoComp->RegisterComponent();
		// FaceLocked uses HMD-relative space: (150,0,0) = 150cm directly in front of the user.
		StereoComp->SetRelativeLocation(FVector(150.f, 0.f, 0.f));
		LoginStereoLayer = StereoComp;
	}

	// Widget renderer — renders UMG widget tree into the RT on a timer
	LoginWidgetRenderer = MakeShared<FWidgetRenderer>(true, false);
	UpdateLoginWidgetRT();

	World->GetTimerManager().SetTimer(
		LoginWidgetUpdateTimerHandle,
		this,
		&UHMVRGameInstance::UpdateLoginWidgetRT,
		1.f / 30.f,
		true
	);

	UE_LOG(LogTemp, Log, TEXT("HMVRGameInstance: Login stereo layer created (1024x768, face-locked 150cm, bLiveTexture=false)"));
}

void UHMVRGameInstance::UpdateLoginWidgetRT()
{
	if (!LoginWidgetRT || !LoginWidgetInstance || !LoginWidgetRenderer.IsValid()) return;

	LoginWidgetRenderer->DrawWidget(
		LoginWidgetRT,
		LoginWidgetInstance->TakeWidget(),
		FVector2D(1024.f, 768.f),
		1.f / 30.f
	);

	// With bLiveTexture=false, notify the compositor to copy the updated RT into its swapchain
	if (LoginStereoLayer.IsValid())
	{
		LoginStereoLayer->MarkStereoLayerDirty();
	}
}

void UHMVRGameInstance::TearDownLoginWidget()
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(LoginWidgetUpdateTimerHandle);
	}

	if (LoginWidgetInstance)
	{
		LoginWidgetInstance->RemoveFromParent();
		LoginWidgetInstance = nullptr;
	}

	if (LoginStereoLayer.IsValid())
	{
		if (AActor* Owner = LoginStereoLayer->GetOwner())
		{
			Owner->Destroy();
		}
		LoginStereoLayer.Reset();
	}

	LoginWidgetRT = nullptr;
	LoginWidgetRenderer.Reset();
}

bool UHMVRGameInstance::HasSavedCredentials() const
{
	return UGameplayStatics::DoesSaveGameExist(CredentialsSaveSlot, 0);
}

FString UHMVRGameInstance::GetCachedUsername() const
{
	return CachedUsername;
}

// ─────────────────────────────────────────────────────────────────────────────

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

	APlayerController* PC = GetFirstLocalPlayerController(GetWorld());
	if (!PC)
	{
		return nullptr;
	}

	UClass* WidgetClass = StatusWidgetClass
		? static_cast<UClass*>(StatusWidgetClass)
		: UHMVRStatusWidget::StaticClass();

	ActiveStatusWidget = CreateWidget<UHMVRStatusWidget>(PC, WidgetClass);
	if (ActiveStatusWidget)
	{
		ActiveStatusWidget->AddToViewport();
		ActiveStatusWidget->OnRetryRequested.AddDynamic(this, &UHMVRGameInstance::StartMatchmaking);
		ActiveStatusWidget->OnCancelRequested.AddDynamic(this, &UHMVRGameInstance::CancelMatchmaking);
	}

	return ActiveStatusWidget;
}
