// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "SessionManager.generated.h"

/**
 * Session state enum (Requirement 5.6)
 */
UENUM(BlueprintType)
enum class ESessionState : uint8
{
	CREATED		UMETA(DisplayName = "Created"),
	ACTIVE		UMETA(DisplayName = "Active"),
	ENDED		UMETA(DisplayName = "Ended"),
	EXPIRED		UMETA(DisplayName = "Expired")
};

/**
 * Interaction event structure
 */
USTRUCT(BlueprintType)
struct FInteractionEvent
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FString EventId;

	UPROPERTY(BlueprintReadOnly)
	FDateTime Timestamp;

	UPROPERTY(BlueprintReadOnly)
	FString PlayerId;

	UPROPERTY(BlueprintReadOnly)
	FString EventType;

	UPROPERTY(BlueprintReadOnly)
	TMap<FString, FString> Data;

	UPROPERTY(BlueprintReadOnly)
	int64 TTL; // Unix timestamp for DynamoDB TTL (72 hours after session end)

	FInteractionEvent()
		: Timestamp(FDateTime::UtcNow())
		, TTL(0)
	{
		EventId = FGuid::NewGuid().ToString();
	}
};

/**
 * Player session structure
 */
USTRUCT(BlueprintType)
struct FPlayerSession
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FString SessionId;

	UPROPERTY(BlueprintReadOnly)
	FString PlayerId;

	UPROPERTY(BlueprintReadOnly)
	FString ShardId;

	UPROPERTY(BlueprintReadOnly)
	ESessionState State;

	UPROPERTY(BlueprintReadOnly)
	FDateTime StartTime;

	UPROPERTY(BlueprintReadOnly)
	FDateTime EndTime;

	UPROPERTY(BlueprintReadOnly)
	TArray<FInteractionEvent> Events;

	UPROPERTY(BlueprintReadOnly)
	TArray<FString> Rewards; // Reward IDs from catalog

	UPROPERTY(BlueprintReadOnly)
	int64 TTL; // Unix timestamp for DynamoDB TTL (72 hours after session end)

	FPlayerSession()
		: State(ESessionState::CREATED)
		, StartTime(FDateTime::UtcNow())
		, TTL(0)
	{
		SessionId = FGuid::NewGuid().ToString();
	}
};

/**
 * Player session summary for persistence
 */
USTRUCT(BlueprintType)
struct FPlayerSessionSummary
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FString SessionId;

	UPROPERTY(BlueprintReadOnly)
	FString PlayerId;

	UPROPERTY(BlueprintReadOnly)
	TArray<FString> Rewards; // Reward IDs granted during session

	UPROPERTY(BlueprintReadOnly)
	FDateTime SessionStartTime;

	UPROPERTY(BlueprintReadOnly)
	FDateTime SessionEndTime;

	FPlayerSessionSummary()
		: SessionStartTime(FDateTime::UtcNow())
		, SessionEndTime(FDateTime::UtcNow())
	{
	}
};

/**
 * Session Manager
 * Implements ephemeral session logic (Requirement 5.1, 5.5, 5.6, 5.7)
 */
UCLASS()
class HYPERMAGEVR_API USessionManager : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * Create a new session (state: CREATED)
	 * @param PlayerId The player ID
	 * @param ShardId The shard ID
	 * @return The created session
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	FPlayerSession CreateSession(const FString& PlayerId, const FString& ShardId);

	/**
	 * Start a session (transition CREATED → ACTIVE)
	 * @param SessionId The session ID
	 * @return True if successful
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	bool StartSession(const FString& SessionId);

	/**
	 * End a session (transition ACTIVE → ENDED)
	 * @param SessionId The session ID
	 * @return True if successful
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	bool EndSession(const FString& SessionId);

	/**
	 * Track a player event during session
	 * @param SessionId The session ID
	 * @param EventType The event type
	 * @param EventData The event data
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	void TrackEvent(const FString& SessionId, const FString& EventType, const TMap<FString, FString>& EventData);

	/**
	 * Add a reward to a session
	 * @param SessionId The session ID
	 * @param RewardId The reward ID
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	void AddReward(const FString& SessionId, const FString& RewardId);

	/**
	 * Generate session summary (for persistence)
	 * @param SessionId The session ID
	 * @return The session summary
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	FPlayerSessionSummary GenerateSessionSummary(const FString& SessionId);

	/**
	 * Discard session gameplay state (keeps only rewards)
	 * @param SessionId The session ID
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	void DiscardSessionState(const FString& SessionId);

	/**
	 * Get session by ID
	 * @param SessionId The session ID
	 * @param OutSession The output session
	 * @return True if found
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	bool GetSession(const FString& SessionId, FPlayerSession& OutSession) const;

	/**
	 * Get session state
	 * @param SessionId The session ID
	 * @return The session state
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	ESessionState GetSessionState(const FString& SessionId) const;

	/**
	 * Calculate TTL timestamp (72 hours from now)
	 * @return Unix timestamp for TTL
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	static int64 CalculateTTL();

	/**
	 * Calculate TTL timestamp from a specific time (72 hours from given time)
	 * @param FromTime The time to calculate from
	 * @return Unix timestamp for TTL
	 */
	UFUNCTION(BlueprintCallable, Category = "Session")
	static int64 CalculateTTLFromTime(const FDateTime& FromTime);

protected:
	// Active sessions (in-memory, ephemeral)
	UPROPERTY()
	TMap<FString, FPlayerSession> ActiveSessions;

	// Helper to transition session state
	bool TransitionState(const FString& SessionId, ESessionState FromState, ESessionState ToState);
};
