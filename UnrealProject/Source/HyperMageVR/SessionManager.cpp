// Copyright 2026 HyperMage. All Rights Reserved.

#include "SessionManager.h"

FPlayerSession USessionManager::CreateSession(const FString& PlayerId, const FString& ShardId)
{
	FPlayerSession NewSession;
	NewSession.SessionId = FGuid::NewGuid().ToString();
	NewSession.PlayerId = PlayerId;
	NewSession.ShardId = ShardId;
	NewSession.State = ESessionState::CREATED;
	NewSession.StartTime = FDateTime::UtcNow();
	NewSession.TTL = 0; // TTL set when session ends

	// Store in active sessions
	ActiveSessions.Add(NewSession.SessionId, NewSession);

	UE_LOG(LogTemp, Log, TEXT("SessionManager: Created session %s for player %s in shard %s"),
		*NewSession.SessionId, *PlayerId, *ShardId);

	return NewSession;
}

bool USessionManager::StartSession(const FString& SessionId)
{
	// Transition CREATED → ACTIVE
	if (TransitionState(SessionId, ESessionState::CREATED, ESessionState::ACTIVE))
	{
		UE_LOG(LogTemp, Log, TEXT("SessionManager: Started session %s"), *SessionId);
		return true;
	}

	UE_LOG(LogTemp, Warning, TEXT("SessionManager: Failed to start session %s - invalid state"), *SessionId);
	return false;
}

bool USessionManager::EndSession(const FString& SessionId)
{
	// Transition ACTIVE → ENDED
	if (!TransitionState(SessionId, ESessionState::ACTIVE, ESessionState::ENDED))
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Failed to end session %s - invalid state"), *SessionId);
		return false;
	}

	// Set end time and calculate TTL (72 hours from now)
	FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (Session)
	{
		Session->EndTime = FDateTime::UtcNow();
		Session->TTL = CalculateTTLFromTime(Session->EndTime);

		// Set TTL on all events
		for (FInteractionEvent& Event : Session->Events)
		{
			Event.TTL = Session->TTL;
		}

		UE_LOG(LogTemp, Log, TEXT("SessionManager: Ended session %s - TTL set to %lld"), 
			*SessionId, Session->TTL);
	}

	return true;
}

void USessionManager::TrackEvent(const FString& SessionId, const FString& EventType, const TMap<FString, FString>& EventData)
{
	FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (!Session)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Cannot track event - session %s not found"), *SessionId);
		return;
	}

	// Only track events for active sessions
	if (Session->State != ESessionState::ACTIVE)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Cannot track event - session %s not active (state: %d)"), 
			*SessionId, (int32)Session->State);
		return;
	}

	// Create event
	FInteractionEvent Event;
	Event.EventId = FGuid::NewGuid().ToString();
	Event.Timestamp = FDateTime::UtcNow();
	Event.PlayerId = Session->PlayerId;
	Event.EventType = EventType;
	Event.Data = EventData;
	Event.TTL = 0; // TTL set when session ends

	// Add to session
	Session->Events.Add(Event);

	UE_LOG(LogTemp, Verbose, TEXT("SessionManager: Tracked event '%s' for session %s (total events: %d)"),
		*EventType, *SessionId, Session->Events.Num());
}

void USessionManager::AddReward(const FString& SessionId, const FString& RewardId)
{
	FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (!Session)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Cannot add reward - session %s not found"), *SessionId);
		return;
	}

	// Check if reward already granted
	if (Session->Rewards.Contains(RewardId))
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Reward '%s' already granted in session %s"), 
			*RewardId, *SessionId);
		return;
	}

	// Add reward
	Session->Rewards.Add(RewardId);

	UE_LOG(LogTemp, Log, TEXT("SessionManager: Added reward '%s' to session %s (total rewards: %d)"),
		*RewardId, *SessionId, Session->Rewards.Num());
}

FPlayerSessionSummary USessionManager::GenerateSessionSummary(const FString& SessionId)
{
	FPlayerSessionSummary Summary;

	const FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (!Session)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Cannot generate summary - session %s not found"), *SessionId);
		return Summary;
	}

	// Copy only persistent data (rewards)
	Summary.SessionId = Session->SessionId;
	Summary.PlayerId = Session->PlayerId;
	Summary.Rewards = Session->Rewards;
	Summary.SessionStartTime = Session->StartTime;
	Summary.SessionEndTime = Session->EndTime;

	UE_LOG(LogTemp, Log, TEXT("SessionManager: Generated summary for session %s - %d rewards"),
		*SessionId, Summary.Rewards.Num());

	return Summary;
}

void USessionManager::DiscardSessionState(const FString& SessionId)
{
	FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (!Session)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Cannot discard state - session %s not found"), *SessionId);
		return;
	}

	// Discard all gameplay state (events, positions, etc.)
	// Keep only rewards for persistence
	int32 EventCount = Session->Events.Num();
	Session->Events.Empty();

	UE_LOG(LogTemp, Log, TEXT("SessionManager: Discarded %d events from session %s - rewards preserved (%d)"),
		EventCount, *SessionId, Session->Rewards.Num());

	// In production, this is where we would:
	// 1. Generate PlayerSessionSummary
	// 2. Send summary to Session API
	// 3. Remove session from ActiveSessions
	// 4. DynamoDB TTL will auto-delete after 72 hours
}

bool USessionManager::GetSession(const FString& SessionId, FPlayerSession& OutSession) const
{
	const FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (Session)
	{
		OutSession = *Session;
		return true;
	}
	return false;
}

ESessionState USessionManager::GetSessionState(const FString& SessionId) const
{
	const FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (Session)
	{
		return Session->State;
	}
	return ESessionState::EXPIRED;
}

int64 USessionManager::CalculateTTL()
{
	return CalculateTTLFromTime(FDateTime::UtcNow());
}

int64 USessionManager::CalculateTTLFromTime(const FDateTime& FromTime)
{
	// Calculate 72 hours from the given time
	FTimespan TTLDuration = FTimespan::FromHours(72);
	FDateTime ExpirationTime = FromTime + TTLDuration;

	// Convert to Unix timestamp (seconds since January 1, 1970)
	int64 UnixTimestamp = ExpirationTime.ToUnixTimestamp();

	return UnixTimestamp;
}

bool USessionManager::TransitionState(const FString& SessionId, ESessionState FromState, ESessionState ToState)
{
	FPlayerSession* Session = ActiveSessions.Find(SessionId);
	if (!Session)
	{
		return false;
	}

	// Validate state transition
	if (Session->State != FromState)
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionManager: Invalid state transition for session %s - expected %d, got %d"),
			*SessionId, (int32)FromState, (int32)Session->State);
		return false;
	}

	// Perform transition
	Session->State = ToState;

	UE_LOG(LogTemp, Log, TEXT("SessionManager: Session %s transitioned from %d to %d"),
		*SessionId, (int32)FromState, (int32)ToState);

	return true;
}
