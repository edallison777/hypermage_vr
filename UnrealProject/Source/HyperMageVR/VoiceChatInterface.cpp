// Copyright 2026 HyperMage. All Rights Reserved.

#include "VoiceChatInterface.h"
#include "Engine/World.h"

UVoiceChatManager::UVoiceChatManager()
{
	bIsInitialized = false;
}

bool UVoiceChatManager::Initialize(TScriptInterface<IVoiceChatProvider> Provider)
{
	if (!Provider.GetInterface())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Invalid provider"));
		return false;
	}

	VoiceProvider = Provider;

	// Initialize the provider
	if (!VoiceProvider->Initialize())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Failed to initialize provider"));
		VoiceProvider = nullptr;
		return false;
	}

	bIsInitialized = true;
	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Initialized successfully"));
	return true;
}

void UVoiceChatManager::Shutdown()
{
	if (!bIsInitialized)
	{
		return;
	}

	// Leave channel if currently in one
	if (IsInPartyChannel())
	{
		LeavePartyChannel();
	}

	// Shutdown provider
	if (VoiceProvider.GetInterface())
	{
		VoiceProvider->Shutdown();
		VoiceProvider = nullptr;
	}

	bIsInitialized = false;
	CurrentShardId.Empty();
	CurrentPlayerId.Empty();

	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Shutdown complete"));
}

bool UVoiceChatManager::JoinPartyChannel(const FString& ShardId, const FString& PlayerId)
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Not initialized"));
		return false;
	}

	if (ShardId.IsEmpty() || PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Invalid ShardId or PlayerId"));
		return false;
	}

	// Leave current channel if in one
	if (IsInPartyChannel())
	{
		LeavePartyChannel();
	}

	// Join the party channel for this shard
	// Channel name format: "party_<ShardId>"
	FString ChannelName = FString::Printf(TEXT("party_%s"), *ShardId);

	if (!VoiceProvider->JoinChannel(ChannelName, PlayerId))
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Failed to join channel %s"), *ChannelName);
		return false;
	}

	CurrentShardId = ShardId;
	CurrentPlayerId = PlayerId;

	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Joined party channel for shard %s as player %s"), 
		*ShardId, *PlayerId);

	return true;
}

bool UVoiceChatManager::LeavePartyChannel()
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Not initialized"));
		return false;
	}

	if (!IsInPartyChannel())
	{
		UE_LOG(LogTemp, Warning, TEXT("VoiceChatManager: Not in a party channel"));
		return true; // Not an error
	}

	if (!VoiceProvider->LeaveChannel())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Failed to leave channel"));
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Left party channel for shard %s"), *CurrentShardId);

	CurrentShardId.Empty();
	CurrentPlayerId.Empty();

	return true;
}

bool UVoiceChatManager::IsInPartyChannel() const
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		return false;
	}

	return VoiceProvider->IsInChannel();
}

void UVoiceChatManager::SetMicrophoneMuted(bool bMuted)
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Not initialized"));
		return;
	}

	VoiceProvider->SetMicrophoneMuted(bMuted);
	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Microphone %s"), bMuted ? TEXT("muted") : TEXT("unmuted"));
}

bool UVoiceChatManager::IsMicrophoneMuted() const
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		return true; // Default to muted if not initialized
	}

	return VoiceProvider->IsMicrophoneMuted();
}

void UVoiceChatManager::SetPlayerMuted(const FString& PlayerId, bool bMuted)
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Not initialized"));
		return;
	}

	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("VoiceChatManager: Invalid PlayerId"));
		return;
	}

	VoiceProvider->SetPlayerMuted(PlayerId, bMuted);
	UE_LOG(LogTemp, Log, TEXT("VoiceChatManager: Player %s %s"), 
		*PlayerId, bMuted ? TEXT("muted") : TEXT("unmuted"));
}

bool UVoiceChatManager::IsPlayerMuted(const FString& PlayerId) const
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		return false;
	}

	if (PlayerId.IsEmpty())
	{
		return false;
	}

	return VoiceProvider->IsPlayerMuted(PlayerId);
}

TArray<FString> UVoiceChatManager::GetPlayersInChannel() const
{
	if (!bIsInitialized || !VoiceProvider.GetInterface())
	{
		return TArray<FString>();
	}

	return VoiceProvider->GetPlayersInChannel();
}
