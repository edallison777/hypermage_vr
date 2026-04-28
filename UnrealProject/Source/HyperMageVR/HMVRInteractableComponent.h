// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "HMVRInteractable.h"
#include "Sound/SoundBase.h"
#include "Http.h"
#include "HMVRInteractableComponent.generated.h"

UCLASS(ClassGroup=(HyperMage), meta=(BlueprintSpawnableComponent))
class HYPERMAGEVR_API UHMVRInteractableComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UHMVRInteractableComponent();

	// Unique identifier — must match the object_id in the ScenePlan and world-state DB.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Interactable")
	FString ObjectId;

	// If true, state is written to the world-state API on every transition.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Interactable")
	bool bPersistent = false;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Interactable")
	float AlertRadius = 500.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Interactable")
	float InteractRadius = 150.f;

	// Sound to play on each state transition. Assigned in Blueprint subclass.
	UPROPERTY(EditDefaultsOnly, Category="Audio")
	TMap<EInteractableState, USoundBase*> SoundsByState;

	UPROPERTY(BlueprintAssignable, Category="Interactable")
	FOnInteractableStateChanged OnStateChanged;

	// Server only — call this to drive the state machine.
	// No-op on clients; the replicated State property handles visual sync.
	void TransitionTo(EInteractableState NewState);

	// Async: POST current state to world-state API. No-op if !bPersistent.
	void PersistState();

	// Async: GET state from world-state API and apply it. No-op if !bPersistent.
	void LoadState();

	UFUNCTION(BlueprintCallable, Category="Interactable")
	EInteractableState GetState() const { return State; }

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

private:
	UPROPERTY(ReplicatedUsing=OnRep_State)
	EInteractableState State = EInteractableState::Idle;

	UFUNCTION()
	void OnRep_State();

	void TriggerAudio(EInteractableState ForState);

	void OnPersistResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnected);
	void OnLoadResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnected);

	// Set from HMVRGameMode::InitGame() once world-state Lambda is deployed.
	static FString WorldStateApiUrl;
};
