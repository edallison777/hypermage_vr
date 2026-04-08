// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "HMVRPlayerState.generated.h"

/**
 * Player State for HyperMage VR
 * Holds the authenticated Cognito player ID extracted from the JWT in PreLogin.
 */
UCLASS()
class HYPERMAGEVR_API AHMVRPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	// Cognito sub claim — set from JWT in HMVRGameMode::Login()
	// Named CognitoPlayerId to avoid shadowing APlayerState::PlayerId (int32)
	UPROPERTY(BlueprintReadOnly, Replicated, Category = "Authentication")
	FString CognitoPlayerId;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
};
