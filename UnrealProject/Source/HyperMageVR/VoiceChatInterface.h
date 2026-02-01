// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "VoiceChatInterface.generated.h"

/**
 * Voice Chat Provider Interface
 * Implements Requirement 4.3: Pluggable voice provider interface
 * 
 * This interface allows different voice providers to be plugged in
 * (e.g., Vivox, Agora, custom solutions, or mock providers for testing)
 */
UINTERFACE(MinimalAPI, Blueprintable)
class UVoiceChatProvider : public UInterface
{
	GENERATED_BODY()
};

class IVoiceChatProvider
{
	GENERATED_BODY()

public:
	/**
	 * Initialize the voice provider
	 * @return true if initialization succeeded
	 */
	virtual bool Initialize() = 0;

	/**
	 * Shutdown the voice provider
	 */
	virtual void Shutdown() = 0;

	/**
	 * Join a voice channel
	 * @param ChannelName The name of the channel to join
	 * @param PlayerId The unique ID of the player joining
	 * @return true if join succeeded
	 */
	virtual bool JoinChannel(const FString& ChannelName, const FString& PlayerId) = 0;

	/**
	 * Leave the current voice channel
	 * @return true if leave succeeded
	 */
	virtual bool LeaveChannel() = 0;

	/**
	 * Check if currently in a voice channel
	 * @return true if in a channel
	 */
	virtual bool IsInChannel() const = 0;

	/**
	 * Get the current channel name
	 * @return The channel name, or empty string if not in a channel
	 */
	virtual FString GetCurrentChannel() const = 0;

	/**
	 * Mute/unmute local microphone
	 * @param bMuted true to mute, false to unmute
	 */
	virtual void SetMicrophoneMuted(bool bMuted) = 0;

	/**
	 * Check if local microphone is muted
	 * @return true if muted
	 */
	virtual bool IsMicrophoneMuted() const = 0;

	/**
	 * Mute/unmute a specific player
	 * @param PlayerId The player to mute/unmute
	 * @param bMuted true to mute, false to unmute
	 */
	virtual void SetPlayerMuted(const FString& PlayerId, bool bMuted) = 0;

	/**
	 * Check if a specific player is muted
	 * @param PlayerId The player to check
	 * @return true if muted
	 */
	virtual bool IsPlayerMuted(const FString& PlayerId) const = 0;

	/**
	 * Get list of players in current channel
	 * @return Array of player IDs
	 */
	virtual TArray<FString> GetPlayersInChannel() const = 0;
};

/**
 * Voice Chat Manager
 * Manages party voice communication for the shard
 * Implements Requirements 4.1, 4.2: Party voice communication within each shard
 */
UCLASS()
class HYPERMAGEVR_API UVoiceChatManager : public UObject
{
	GENERATED_BODY()

public:
	UVoiceChatManager();

	/**
	 * Initialize voice chat with a specific provider
	 * @param Provider The voice provider to use
	 * @return true if initialization succeeded
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool Initialize(TScriptInterface<IVoiceChatProvider> Provider);

	/**
	 * Shutdown voice chat
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	void Shutdown();

	/**
	 * Join party voice channel for the shard
	 * Implements Requirement 4.2: All players in shard can hear each other
	 * @param ShardId The shard ID to join
	 * @param PlayerId The player's unique ID
	 * @return true if join succeeded
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool JoinPartyChannel(const FString& ShardId, const FString& PlayerId);

	/**
	 * Leave the current party voice channel
	 * @return true if leave succeeded
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool LeavePartyChannel();

	/**
	 * Check if currently in a party channel
	 * @return true if in a channel
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool IsInPartyChannel() const;

	/**
	 * Mute/unmute local microphone
	 * @param bMuted true to mute, false to unmute
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	void SetMicrophoneMuted(bool bMuted);

	/**
	 * Check if local microphone is muted
	 * @return true if muted
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool IsMicrophoneMuted() const;

	/**
	 * Mute/unmute a specific player
	 * @param PlayerId The player to mute/unmute
	 * @param bMuted true to mute, false to unmute
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	void SetPlayerMuted(const FString& PlayerId, bool bMuted);

	/**
	 * Check if a specific player is muted
	 * @param PlayerId The player to check
	 * @return true if muted
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	bool IsPlayerMuted(const FString& PlayerId) const;

	/**
	 * Get list of players in current channel
	 * @return Array of player IDs
	 */
	UFUNCTION(BlueprintCallable, Category = "Voice Chat")
	TArray<FString> GetPlayersInChannel() const;

	/**
	 * Get the current voice provider
	 * @return The voice provider interface
	 */
	TScriptInterface<IVoiceChatProvider> GetProvider() const { return VoiceProvider; }

protected:
	// The voice provider implementation
	UPROPERTY()
	TScriptInterface<IVoiceChatProvider> VoiceProvider;

	// Current shard ID
	FString CurrentShardId;

	// Current player ID
	FString CurrentPlayerId;

	// Initialization state
	bool bIsInitialized = false;
};
