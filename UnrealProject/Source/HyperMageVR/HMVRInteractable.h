// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "HMVRInteractable.generated.h"

UENUM(BlueprintType)
enum class EInteractableState : uint8
{
	Idle      UMETA(DisplayName = "Idle"),
	Alert     UMETA(DisplayName = "Alert"),
	Active    UMETA(DisplayName = "Active"),
	Resolved  UMETA(DisplayName = "Resolved"),
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnInteractableStateChanged, EInteractableState, NewState);

UINTERFACE(MinimalAPI, Blueprintable)
class UHMVRInteractable : public UInterface
{
	GENERATED_BODY()
};

class HYPERMAGEVR_API IHMVRInteractable
{
	GENERATED_BODY()

public:
	virtual void OnPlayerApproach(APlayerController* Player, float Distance) {}
	virtual void OnPlayerInteract(APlayerController* Player) {}
	virtual void OnDamageReceived(float Amount, AActor* Source) {}
	virtual void OnCollected(APlayerController* Player) {}
};
