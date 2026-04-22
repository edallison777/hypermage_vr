// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "VoiceChatInterface.h"
#include "HMVRStatusWidget.h"
#include "HMVRLoginWidget.h"
#include "HMVRSaveGame.h"
#include "Http.h"
#include "HMVRGameInstance.generated.h"

class FGameLiftServerSDKModule; // incomplete type; only used as pointer — no header needed

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAutoLoginComplete, bool, bSuccess, const FString&, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnLoginResult,      bool, bSuccess, const FString&, ErrorMessage);
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
	virtual void OnStart() override;
	virtual void Shutdown() override;

	// Authentication
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	void Login(const FString& Username, const FString& Password);

	UFUNCTION(BlueprintCallable, Category = "Authentication")
	void SetJWTToken(const FString& Token);

	UFUNCTION(BlueprintCallable, Category = "Authentication")
	FString GetJWTToken() const { return JWTToken; }

	/**
	 * Call this from Blueprint immediately after a successful manual login.
	 * Persists the refresh token so the next launch skips the login screen.
	 */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	void SetRefreshToken(const FString& Token, const FString& Username = TEXT(""));

	/** Remove saved credentials (logout or token revocation). */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	void ClearSavedCredentials();

	/** True if a saved refresh token exists on disk (before auto-login resolves). */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	bool HasSavedCredentials() const;

	/** Username cached from last login — useful for "Welcome back" UI. */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	FString GetCachedUsername() const;

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

	/**
	 * Fired once on launch after the auto-login attempt completes.
	 * bSuccess=true  → JWTToken is set, proceed directly to matchmaking.
	 * bSuccess=false → no saved credentials or token expired, show login UI.
	 */
	UPROPERTY(BlueprintAssignable, Category = "Authentication")
	FOnAutoLoginComplete OnAutoLoginComplete;

	/** Fired after a manual Login() call completes. */
	UPROPERTY(BlueprintAssignable, Category = "Authentication")
	FOnLoginResult OnLoginResult;

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

	// Auto-login
	void TryAutoLogin();
	void OnTokenRefreshResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
	void SaveCredentials(const FString& RefreshToken, const FString& Username);

	// Manual login
	void OnLoginResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);

	// UI flow
	void HandleAutoLoginResult(bool bSuccess, const FString& ErrorMessage);
	void ShowLoginWidget();

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

	// GameLift SDK access for game mode (server only; no-op on client builds)
	FGameLiftServerSDKModule* GetGameLiftSdkModule() const { return GameLiftSdkModule; }
	bool IsGameLiftInitialized() const { return bGameLiftInitialized; }
	FString GetGameLiftSessionId() const { return GameLiftSessionId; }

protected:
	void InitializeGameLift();

private:
	FGameLiftServerSDKModule* GameLiftSdkModule = nullptr;
	bool bGameLiftInitialized = false;
	FString GameLiftSessionId;

	// Credential persistence
	static const FString CredentialsSaveSlot;
	FString CachedUsername;
	FString PendingLoginUsername;

	// Auto-login result state (set in Init/async, consumed in OnStart)
	bool bAutoLoginAttempted = false;
	bool bAutoLoginSucceeded = false;
	FString AutoLoginError;
	bool bOnStartFired = false;

	// Matchmaking HTTP polling state
	FTimerHandle MatchmakingPollTimerHandle;
	int32 MatchmakingPollAttempt = 0;
	static constexpr int32 MaxMatchmakingPollAttempts = 40; // 2 min at 3s intervals

	// Login widget retry — defers ShowLoginWidget until PlayerController is spawned
	FTimerHandle ShowLoginWidgetRetryHandle;

	// Session API base URL (POST /matchmaking/start, GET /matchmaking/status/{id}, DELETE /matchmaking/cancel/{id})
	const FString SessionApiBaseUrl = TEXT("https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev");
};
