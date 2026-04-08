// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "VoiceChatInterface.h"
#include "Http.h"
#include "HMVRGameInstance.generated.h"

class FGameLiftServerSDKModule;

/**
 * Game Instance for managing session state and authentication
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

	// Connection callbacks
	void OnConnectionSuccess();
	void OnConnectionFailure(const FString& ErrorMessage);

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

	// Session API base URL (POST /matchmaking/start, GET /matchmaking/status/{id})
	const FString SessionApiBaseUrl = TEXT("https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev");
};
