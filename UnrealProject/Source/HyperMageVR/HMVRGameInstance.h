// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "VoiceChatInterface.h"
#include "HMVRStatusWidget.h"
#include "Http.h"
#include "HMVRGameInstance.generated.h"

class FGameLiftServerSDKModule;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMatchmakingStatusChanged, const FString&, Status);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMatchmakingError,         const FString&, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnConnectionEstablished);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnConnectionError, const FString&, ErrorMessage);

/**
 * Game Instance for managing session state and authentication.
 *
 * Broadcasts Blueprint-assignable delegates on all matchmaking / connection state
 * changes so UI widgets can react without polling.
 */
UCLASS()
class HYPERMAGEVR_API UHMVRGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void Init() override;
	virtual void Shutdown() override;

	// Authentication
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	void SetJWTToken(const FString& Token);

	UFUNCTION(BlueprintCallable, Category = "Authentication")
	FString GetJWTToken() const { return JWTToken; }

	// Session management
	UFUNCTION(BlueprintCallable, Category = "Session")
	void SetPlayerSessionId(const FString& SessionId);

	UFUNCTION(BlueprintCallable, Category = "Session")
	FString GetPlayerSessionId() const { return PlayerSessionId; }

	// Matchmaking
	UFUNCTION(BlueprintCallable, Category = "Matchmaking")
	void StartMatchmaking();

	UFUNCTION(BlueprintCallable, Category = "Matchmaking")
	void CancelMatchmaking();

	// Connection
	UFUNCTION(BlueprintCallable, Category = "Connection")
	void ConnectToGameServer(const FString& ServerAddress, int32 Port);

	// Navigation
	UFUNCTION(BlueprintCallable, Category = "Navigation")
	void ReturnToMainMenu();

	// ── Delegates (bind in Blueprint or C++) ────────────────────────────────

	/** Fired when matchmaking status changes (e.g. "SEARCHING", "COMPLETED", "CANCELLED"). */
	UPROPERTY(BlueprintAssignable, Category = "Matchmaking")
	FOnMatchmakingStatusChanged OnMatchmakingStatusChanged;

	/** Fired when matchmaking fails — carries the human-readable error message. */
	UPROPERTY(BlueprintAssignable, Category = "Matchmaking")
	FOnMatchmakingError OnMatchmakingError;

	/** Fired when the game server connection is successfully established. */
	UPROPERTY(BlueprintAssignable, Category = "Connection")
	FOnConnectionEstablished OnConnectionEstablished;

	/** Fired when the game server connection fails — carries the error message. */
	UPROPERTY(BlueprintAssignable, Category = "Connection")
	FOnConnectionError OnConnectionError;

	// ── Status Widget ────────────────────────────────────────────────────────

	/**
	 * Blueprint subclass of UHMVRStatusWidget to instantiate for in-game status UI.
	 * Set this on the GameInstance Blueprint defaults.
	 */
	UPROPERTY(EditDefaultsOnly, Category = "UI")
	TSubclassOf<UHMVRStatusWidget> StatusWidgetClass;

	/** Currently active status widget instance (nullptr if not yet created). */
	UPROPERTY(BlueprintReadOnly, Category = "UI")
	UHMVRStatusWidget* ActiveStatusWidget = nullptr;

	/** Level name to travel to when returning to the main menu. */
	UPROPERTY(EditDefaultsOnly, Category = "Navigation")
	FName MainMenuLevelName = FName(TEXT("MainMenu"));

protected:
	// Authentication state
	UPROPERTY(BlueprintReadOnly, Category = "Authentication")
	FString JWTToken;

	UPROPERTY(BlueprintReadOnly, Category = "Authentication")
	FString PlayerId;

	// Session state
	UPROPERTY(BlueprintReadOnly, Category = "Session")
	FString PlayerSessionId;

	UPROPERTY(BlueprintReadOnly, Category = "Session")
	FString MatchmakingTicketId;

	// Matchmaking callbacks
	void OnMatchmakingSuccess(const FString& ServerAddress, int32 Port, const FString& SessionId);
	void OnMatchmakingFailure(const FString& ErrorMessage);

	// Matchmaking HTTP polling
	void PollMatchmakingStatus();
	void OnStartMatchmakingResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
	void OnMatchmakingStatusResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
	void OnCancelMatchmakingResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);

	// Connection callbacks
	void OnConnectionSuccess();
	void OnConnectionFailure(const FString& ErrorMessage);

	// UI helpers
	UHMVRStatusWidget* EnsureStatusWidget();

	// Voice chat manager
	UPROPERTY()
	UVoiceChatManager* VoiceChatManager;

public:
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	UVoiceChatManager* GetVoiceChatManager() const { return VoiceChatManager; }

	// GameLift SDK access for game mode
	FGameLiftServerSDKModule* GetGameLiftSdkModule() const { return GameLiftSdkModule; }
	bool IsGameLiftInitialized() const { return bGameLiftInitialized; }
	FString GetGameLiftSessionId() const { return GameLiftSessionId; }

protected:
	void InitializeGameLift();

private:
	FGameLiftServerSDKModule* GameLiftSdkModule = nullptr;
	bool bGameLiftInitialized = false;
	FString GameLiftSessionId;

	// Matchmaking HTTP polling state
	FTimerHandle MatchmakingPollTimerHandle;
	int32 MatchmakingPollAttempt = 0;
	static constexpr int32 MaxMatchmakingPollAttempts = 40; // 2 min at 3s intervals

	// Session API base URL (POST /matchmaking/start, GET /matchmaking/status/{id}, DELETE /matchmaking/cancel/{id})
	const FString SessionApiBaseUrl = TEXT("https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev");
};
