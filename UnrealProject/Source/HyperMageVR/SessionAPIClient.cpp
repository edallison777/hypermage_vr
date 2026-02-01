// Copyright 2026 HyperMageVR. All Rights Reserved.

#include "SessionAPIClient.h"

bool USessionAPIClient::SendSessionSummary(const FPlayerSessionSummary& Summary)
{
	if (bMockMode)
	{
		// Mock implementation - just log
		UE_LOG(LogTemp, Log, TEXT("SessionAPIClient (MOCK): Sending session summary for session %s, player %s, rewards: %d"),
			*Summary.SessionId, *Summary.PlayerId, Summary.Rewards.Num());

		// Log rewards
		for (const FString& RewardId : Summary.Rewards)
		{
			UE_LOG(LogTemp, Log, TEXT("  - Reward: %s"), *RewardId);
		}

		return true;
	}

	// Real implementation (Task 15.4)
	// POST /session-summary
	// {
	//   "sessionId": "...",
	//   "playerId": "...",
	//   "rewards": ["reward1", "reward2"],
	//   "sessionStartTime": "...",
	//   "sessionEndTime": "..."
	// }

	UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: Real API not implemented yet (Task 15.4)"));
	return false;
}

bool USessionAPIClient::SendInteractionEvent(const FInteractionEvent& Event)
{
	if (bMockMode)
	{
		// Mock implementation - just log
		UE_LOG(LogTemp, Verbose, TEXT("SessionAPIClient (MOCK): Sending event %s for player %s, type: %s"),
			*Event.EventId, *Event.PlayerId, *Event.EventType);

		return true;
	}

	// Real implementation (Task 15.4)
	// POST /interaction-events
	// {
	//   "eventId": "...",
	//   "timestamp": "...",
	//   "playerId": "...",
	//   "eventType": "...",
	//   "data": {...},
	//   "ttl": 1234567890
	// }

	UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: Real API not implemented yet (Task 15.4)"));
	return false;
}

void USessionAPIClient::SetEndpointURL(const FString& URL)
{
	EndpointURL = URL;
	UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: Endpoint URL set to %s"), *URL);

	// Disable mock mode if URL is set
	if (!URL.IsEmpty())
	{
		bMockMode = false;
	}
}
