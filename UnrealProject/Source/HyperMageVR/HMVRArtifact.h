// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HMVRInteractable.h"
#include "HMVRInteractableComponent.h"
#include "HMVRArtifact.generated.h"

class UStaticMeshComponent;
class USphereComponent;
class URotatingMovementComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnArtifactCollected, AActor*, Artifact, APlayerController*, Collector);

UCLASS()
class HYPERMAGEVR_API AHMVRArtifact : public AActor, public IHMVRInteractable
{
	GENERATED_BODY()

public:
	AHMVRArtifact();

	// IHMVRInteractable
	virtual void OnPlayerApproach(APlayerController* Player, float Distance) override;
	virtual void OnPlayerInteract(APlayerController* Player) override;
	virtual void OnDamageReceived(float Amount, AActor* Source) override {}
	virtual void OnCollected(APlayerController* Player) override;

	// Matches the asset_id in the DynamoDB asset catalogue (Phase 7).
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Artifact")
	FString ArtifactId;

	// If true, collecting this artefact grants the player the named ability.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Artifact")
	bool bGrantsAbility = false;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Artifact",
	          meta=(EditCondition="bGrantsAbility"))
	FString AbilityId;

	// Slow idle rotation to draw player attention.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Artifact")
	bool bRotates = true;

	UPROPERTY(BlueprintAssignable, Category="Artifact")
	FOnArtifactCollected OnArtifactCollected;

	UFUNCTION(BlueprintImplementableEvent, Category="Artifact")
	void BP_OnCollected(APlayerController* Collector);

	UFUNCTION(BlueprintImplementableEvent, Category="Interactable")
	void BP_OnStateChanged(EInteractableState NewState);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interactable")
	UHMVRInteractableComponent* Interactable;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Mesh")
	UStaticMeshComponent* Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interaction")
	USphereComponent* PickupSphere;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Movement")
	URotatingMovementComponent* RotatingMovement;

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnInteractableStateChanged(EInteractableState NewState);
};
