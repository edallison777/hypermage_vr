// Copyright 2026 HyperMage. All Rights Reserved.

#include "MockVoiceProvider.h"

UMockVoiceProvider::UMockVoiceProvider()
{
	bIsInitialized = false;
	bInChannel = false;
	bMicrophoneMuted = false;
}

bool UMockVoiceProvider::Initialize()
{
	if (bIsInitialized)
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Already initialized"));
		return true;
	}

	bIsInitialized = true;
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Initialized (mock mode)"));
	return true;
}

void UMockVoiceProvider::Shutdown()
{
	if (!bIsInitialized)
	{
		return;
	}

	// Leave channel if in one
	if (bInChannel)
	{
		LeaveChannel();
	}

	bIsInitialized = false;
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Shutdown (mock mode)"));
}

bool UMockVoiceProvider::JoinChannel(const FString& ChannelName, const FString& PlayerId)
{
	if (!bIsInitialized)
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Not initialized"));
		return false;
	}

	if (ChannelName.IsEmpty() || PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Invalid ChannelName or PlayerId"));
		return false;
	}

	// Leave current channel if in one
	if (bInChannel)
	{
		LeaveChannel();
	}

	// Simulate joining the channel
	CurrentChannelName = ChannelName;
	LocalPlayerId = PlayerId;
	bInChannel = true;

	// Add local player to the channel
	PlayersInChannel.Add(PlayerId);

	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Joined channel '%s' as player '%s' (mock mode)"), 
		*ChannelName, *PlayerId);

	return true;
}

bool UMockVoiceProvider::LeaveChannel()
{
	if (!bIsInitialized)
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Not initialized"));
		return false;
	}

	if (!bInChannel)
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Not in a channel"));
		return true; // Not an error
	}

	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Left channel '%s' (mock mode)"), *CurrentChannelName);

	// Clear channel state
	CurrentChannelName.Empty();
	LocalPlayerId.Empty();
	bInChannel = false;
	PlayersInChannel.Empty();
	MutedPlayers.Empty();

	return true;
}

bool UMockVoiceProvider::IsInChannel() const
{
	return bInChannel;
}

FString UMockVoiceProvider::GetCurrentChannel() const
{
	return CurrentChannelName;
}

void UMockVoiceProvider::SetMicrophoneMuted(bool bMuted)
{
	if (!bIsInitialized)
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Not initialized"));
		return;
	}

	bMicrophoneMuted = bMuted;
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Microphone %s (mock mode)"), 
		bMuted ? TEXT("muted") : TEXT("unmuted"));
}

bool UMockVoiceProvider::IsMicrophoneMuted() const
{
	return bMicrophoneMuted;
}

void UMockVoiceProvider::SetPlayerMuted(const FString& PlayerId, bool bMuted)
{
	if (!bIsInitialized)
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Not initialized"));
		return;
	}

	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Invalid PlayerId"));
		return;
	}

	if (bMuted)
	{
		MutedPlayers.Add(PlayerId);
		UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Muted player '%s' (mock mode)"), *PlayerId);
	}
	else
	{
		MutedPlayers.Remove(PlayerId);
		UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Unmuted player '%s' (mock mode)"), *PlayerId);
	}
}

bool UMockVoiceProvider::IsPlayerMuted(const FString& PlayerId) const
{
	return MutedPlayers.Contains(PlayerId);
}

TArray<FString> UMockVoiceProvider::GetPlayersInChannel() const
{
	return PlayersInChannel;
}

void UMockVoiceProvider::SimulatePlayerJoined(const FString& PlayerId)
{
	if (!bInChannel)
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Not in a channel, cannot simulate player join"));
		return;
	}

	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Invalid PlayerId"));
		return;
	}

	if (PlayersInChannel.Contains(PlayerId))
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Player '%s' already in channel"), *PlayerId);
		return;
	}

	PlayersInChannel.Add(PlayerId);
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Simulated player '%s' joined channel (mock mode)"), *PlayerId);
}

void UMockVoiceProvider::SimulatePlayerLeft(const FString& PlayerId)
{
	if (!bInChannel)
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Not in a channel, cannot simulate player leave"));
		return;
	}

	if (PlayerId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("MockVoiceProvider: Invalid PlayerId"));
		return;
	}

	if (!PlayersInChannel.Contains(PlayerId))
	{
		UE_LOG(LogTemp, Warning, TEXT("MockVoiceProvider: Player '%s' not in channel"), *PlayerId);
		return;
	}

	PlayersInChannel.Remove(PlayerId);
	MutedPlayers.Remove(PlayerId); // Clean up mute state
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Simulated player '%s' left channel (mock mode)"), *PlayerId);
}

bool UMockVoiceProvider::IsPlayerInChannel(const FString& PlayerId) const
{
	return PlayersInChannel.Contains(PlayerId);
}

void UMockVoiceProvider::ClearSimulatedPlayers()
{
	// Keep local player, remove all others
	PlayersInChannel.Empty();
	if (!LocalPlayerId.IsEmpty())
	{
		PlayersInChannel.Add(LocalPlayerId);
	}
	MutedPlayers.Empty();
	UE_LOG(LogTemp, Log, TEXT("MockVoiceProvider: Cleared simulated players (mock mode)"));
}
