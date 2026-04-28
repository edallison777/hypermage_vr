// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HMVRInteractable.h"
#include "HMVRInteractableComponent.h"
#include "HMVRMachinery.generated.h"

class UStaticMeshComponent;
class USphereComponent;

UENUM(BlueprintType)
enum class EMachinerySubState : uint8
{
	Locked     UMETA(DisplayName = "Locked"),
	Unlocking  UMETA(DisplayName = "Unlocking"),
	Open       UMETA(DisplayName = "Open"),
};

UCLASS()
class HYPERMAGEVR_API AHMVRMachinery : public AActor, public IHMVRInteractable
{
	GENERATED_BODY()

public:
	AHMVRMachinery();

	// IHMVRInteractable
	virtual void OnPlayerApproach(APlayerController* Player, float Distance) override;
	virtual void OnPlayerInteract(APlayerController* Player) override;
	virtual void OnDamageReceived(float Amount, AActor* Source) override {}
	virtual void OnCollected(APlayerController* Player) override {}

	// If true the player must carry an item whose ID matches RequiredKeyId.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Machinery")
	bool bRequiresKey = false;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Machinery",
	          meta=(EditCondition="bRequiresKey"))
	FString RequiredKeyId;

	// Seconds between player interaction and Open state.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Machinery")
	float TriggerDelay = 2.f;

	UPROPERTY(BlueprintReadOnly, Replicated, Category="Machinery")
	EMachinerySubState MachinerySubState = EMachinerySubState::Locked;

	UFUNCTION(BlueprintImplementableEvent, Category="Machinery")
	void BP_OnTriggered();

	UFUNCTION(BlueprintImplementableEvent, Category="Machinery")
	void BP_OnOpened();

	UFUNCTION(BlueprintImplementableEvent, Category="Interactable")
	void BP_OnStateChanged(EInteractableState NewState);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interactable")
	UHMVRInteractableComponent* Interactable;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Mesh")
	UStaticMeshComponent* Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interaction")
	USphereComponent* InteractionSphere;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	virtual void BeginPlay() override;

private:
	FTimerHandle UnlockTimerHandle;

	UFUNCTION()
	void OnUnlockTimerComplete();

	UFUNCTION()
	void OnInteractableStateChanged(EInteractableState NewState);
};
