// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "JWTValidator.h"
#include "SessionManager.h"
#include "RewardSystem.h"
#include "SessionAPIClient.h"
#include "HMVRGameMode.generated.h"

/**
 * Server-authoritative Game Mode for VR Multiplayer
 * Implements Requirement 2.1: Dedicated server authoritative architecture
 */
UCLASS()
class HYPERMAGEVR_API AHMVRGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AHMVRGameMode();

	// GameMode overrides
	virtual void PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
	virtual APlayerController* Login(UPlayer* NewPlayer, ENetRole InRemoteRole, const FString& Portal, const FString& Options, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
	virtual void Logout(AController* Exiting) override;
	virtual void PostLogin(APlayerController* NewPlayer) override;
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

	// Player capacity management (Requirement 2.2)
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Server")
	int32 MaxPlayers = 15;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Server")
	int32 MinPlayers = 10;

	// Get current player count
	UFUNCTION(BlueprintCallable, Category = "Server")
	int32 GetCurrentPlayerCount() const;

	// Check if server can accept more players
	UFUNCTION(BlueprintCallable, Category = "Server")
	bool CanAcceptNewPlayer() const;

protected:
	// JWT authentication (Requirement 3.1-3.4)
	bool ValidateJWTToken(const FString& Token, FString& OutPlayerId, FString& OutErrorMessage);

	// GameLift integration (Requirement 2.4)
	void InitializeGameLift();
	void ReportServerHealth();
	bool ValidatePlayerSession(const FString& PlayerSessionId, FString& OutErrorMessage);
	void AcceptPlayerSession(const FString& PlayerSessionId);
	void RemovePlayerSession(const FString& PlayerSessionId);

	// Session management
	void OnPlayerJoined(APlayerController* NewPlayer);
	void OnPlayerLeft(AController* ExitingPlayer);

	// Reward system
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	void GrantRewardToPlayer(APlayerController* Player, const FString& RewardId);

	// Session manager
	UFUNCTION(BlueprintCallable, Category = "Session")
	USessionManager* GetSessionManager() const { return SessionManager; }

	// Reward system
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	URewardSystem* GetRewardSystem() const { return RewardSystem; }

	// Session API client
	UFUNCTION(BlueprintCallable, Category = "Session API")
	USessionAPIClient* GetSessionAPIClient() const { return SessionAPIClient; }

private:
	// Track connected players
	TArray<TWeakObjectPtr<APlayerController>> ConnectedPlayers;

	// Session manager
	UPROPERTY()
	USessionManager* SessionManager;

	// Reward system
	UPROPERTY()
	URewardSystem* RewardSystem;

	// Session API client
	UPROPERTY()
	USessionAPIClient* SessionAPIClient;

	// Player session tracking (PlayerId -> SessionId)
	TMap<FString, FString> PlayerToSessionMap;

	// GameLift SDK integration
	bool bGameLiftInitialized = false;
	bool bGameLiftProcessReady = false;
	FTimerHandle HealthReportTimerHandle;
	
	// Track player sessions for GameLift
	TMap<FString, FString> PlayerSessionMap; // PlayerSessionId -> PlayerId

	// Session tracking
	FString CurrentSessionId;
	FDateTime SessionStartTime;
};
