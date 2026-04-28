// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HMVRInteractable.h"
#include "HMVRInteractableComponent.h"
#include "HMVREnvironmental.generated.h"

class USphereComponent;

UCLASS()
class HYPERMAGEVR_API AHMVREnvironmental : public AActor, public IHMVRInteractable
{
	GENERATED_BODY()

public:
	AHMVREnvironmental();

	// IHMVRInteractable
	virtual void OnPlayerApproach(APlayerController* Player, float Distance) override;
	virtual void OnPlayerInteract(APlayerController* Player) override;
	virtual void OnDamageReceived(float Amount, AActor* Source) override {}
	virtual void OnCollected(APlayerController* Player) override {}

	// Trigger the event sequence. Can be called externally (e.g. by a puzzle system).
	UFUNCTION(BlueprintCallable, Category="Environmental")
	void Trigger(AActor* Instigator = nullptr);

	// Player enters this radius to auto-trigger (if bAutoTrigger=true).
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Environmental")
	float TriggerRadius = 400.f;

	// Trigger fires when a player enters TriggerRadius.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Environmental")
	bool bAutoTrigger = true;

	// If true, can only be triggered once per session.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Environmental")
	bool bOneShot = true;

	// How long the event sequence runs before transitioning to Resolved.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Environmental")
	float EventSequenceDuration = 5.f;

	UFUNCTION(BlueprintImplementableEvent, Category="Environmental")
	void BP_OnTriggered(AActor* Instigator);

	UFUNCTION(BlueprintImplementableEvent, Category="Environmental")
	void BP_OnResolved();

	UFUNCTION(BlueprintImplementableEvent, Category="Interactable")
	void BP_OnStateChanged(EInteractableState NewState);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interactable")
	UHMVRInteractableComponent* Interactable;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Trigger")
	USphereComponent* TriggerSphere;

protected:
	virtual void BeginPlay() override;

private:
	bool bTriggered = false;
	FTimerHandle SequenceTimerHandle;

	UFUNCTION()
	void OnTriggerOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor,
	                           UPrimitiveComponent* OtherComp, int32 OtherBodyIndex,
	                           bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void OnSequenceComplete();

	UFUNCTION()
	void OnInteractableStateChanged(EInteractableState NewState);
};
