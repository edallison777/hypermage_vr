// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "HMVRSaveGame.generated.h"

/**
 * Persists the Cognito refresh token between sessions so the player does not
 * need to re-enter credentials on every launch.
 *
 * Stored in the app's private sandbox via UGameplayStatics::SaveGameToSlot.
 * The refresh token is valid for 30 days (Cognito default); it is cleared
 * automatically when exchange fails (expired or revoked).
 */
UCLASS()
class HYPERMAGEVR_API UHMVRSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	/** Cognito refresh token — exchanged for a fresh access token on launch. */
	UPROPERTY()
	FString RefreshToken;

	/** Display name / username cached for UI ("Welcome back, <name>"). */
	UPROPERTY()
	FString CachedUsername;

	/** Unix timestamp when these credentials were saved. */
	UPROPERTY()
	int64 SavedAt = 0;
};
