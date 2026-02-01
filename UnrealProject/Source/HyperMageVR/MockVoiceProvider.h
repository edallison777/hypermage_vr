// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "VoiceChatInterface.h"
#include "MockVoiceProvider.generated.h"

/**
 * Mock Voice Provider for Testing
 * Implements Requirement 4.4: Support mock voice provider for testing
 * 
 * This provider simulates voice connections without actual audio routing.
 * Useful for:
 * - Local development without voice infrastructure
 * - Automated testing of voice chat logic
 * - Debugging voice channel management
 */
UCLASS()
class HYPERMAGEVR_API UMockVoiceProvider : public UObject, public IVoiceChatProvider
{
	GENERATED_BODY()

public:
	UMockVoiceProvider();

	// IVoiceChatProvider interface
	virtual bool Initialize() override;
	virtual void Shutdown() override;
	virtual bool JoinChannel(const FString& ChannelName, const FString& PlayerId) override;
	virtual bool LeaveChannel() override;
	virtual bool IsInChannel() const override;
	virtual FString GetCurrentChannel() const override;
	virtual void SetMicrophoneMuted(bool bMuted) override;
	virtual bool IsMicrophoneMuted() const override;
	virtual void SetPlayerMuted(const FString& PlayerId, bool bMuted) override;
	virtual bool IsPlayerMuted(const FString& PlayerId) const override;
	virtual TArray<FString> GetPlayersInChannel() const override;

	// Mock-specific functionality for testing
	
	/**
	 * Simulate another player joining the channel
	 * @param PlayerId The player ID to add
	 */
	UFUNCTION(BlueprintCallable, Category = "Mock Voice")
	void SimulatePlayerJoined(const FString& PlayerId);

	/**
	 * Simulate another player leaving the channel
	 * @param PlayerId The player ID to remove
	 */
	UFUNCTION(BlueprintCallable, Category = "Mock Voice")
	void SimulatePlayerLeft(const FString& PlayerId);

	/**
	 * Get the number of simulated players in the channel
	 * @return The player count
	 */
	UFUNCTION(BlueprintCallable, Category = "Mock Voice")
	int32 GetSimulatedPlayerCount() const { return PlayersInChannel.Num(); }

	/**
	 * Check if a specific player is in the channel
	 * @param PlayerId The player to check
	 * @return true if the player is in the channel
	 */
	UFUNCTION(BlueprintCallable, Category = "Mock Voice")
	bool IsPlayerInChannel(const FString& PlayerId) const;

	/**
	 * Clear all simulated players (for testing)
	 */
	UFUNCTION(BlueprintCallable, Category = "Mock Voice")
	void ClearSimulatedPlayers();

protected:
	// Initialization state
	bool bIsInitialized = false;

	// Current channel state
	FString CurrentChannelName;
	FString LocalPlayerId;
	bool bInChannel = false;

	// Audio state
	bool bMicrophoneMuted = false;

	// Players in the current channel (simulated)
	UPROPERTY()
	TArray<FString> PlayersInChannel;

	// Muted players (local mute list)
	UPROPERTY()
	TSet<FString> MutedPlayers;
};
