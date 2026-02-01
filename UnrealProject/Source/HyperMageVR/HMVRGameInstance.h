// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "VoiceChatInterface.h"
#include "HMVRGameInstance.generated.h"

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

	// Connection callbacks
	void OnConnectionSuccess();
	void OnConnectionFailure(const FString& ErrorMessage);

	// Voice chat manager
	UPROPERTY()
	UVoiceChatManager* VoiceChatManager;

public:
	/**
	 * Get the voice chat manager
	 * @return The voice chat manager instance
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	UVoiceChatManager* GetVoiceChatManager() const { return VoiceChatManager; }
};
