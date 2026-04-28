// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "HMVRInteractable.h"
#include "HMVRInteractableComponent.h"
#include "HMVRCreature.generated.h"

class USphereComponent;
class UBehaviorTree;
class AHMVRCreatureAIController;

UENUM(BlueprintType)
enum class ECreatureSubState : uint8
{
	Patrol  UMETA(DisplayName = "Patrol"),
	Chase   UMETA(DisplayName = "Chase"),
	Attack  UMETA(DisplayName = "Attack"),
};

UCLASS()
class HYPERMAGEVR_API AHMVRCreature : public ACharacter, public IHMVRInteractable
{
	GENERATED_BODY()

public:
	AHMVRCreature();

	// IHMVRInteractable
	virtual void OnPlayerApproach(APlayerController* Player, float Distance) override;
	virtual void OnPlayerInteract(APlayerController* Player) override;
	virtual void OnDamageReceived(float Amount, AActor* Source) override;
	virtual void OnCollected(APlayerController* Player) override {}

	virtual float TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent,
	                         AController* EventInstigator, AActor* DamageCauser) override;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// ── Combat ──────────────────────────────────────────────────────────────────

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat")
	float MaxHealth = 100.f;

	UPROPERTY(BlueprintReadOnly, Replicated, Category="Combat")
	float Health = 100.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat")
	float AttackDamage = 15.f;

	// ── AI ──────────────────────────────────────────────────────────────────────

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="AI")
	UBehaviorTree* BehaviorTreeAsset;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="AI")
	float DetectionRadius = 800.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="AI")
	float AttackRadius = 200.f;

	UPROPERTY(BlueprintReadOnly, Replicated, Category="AI")
	ECreatureSubState CreatureSubState = ECreatureSubState::Patrol;

	void SetCreatureSubState(ECreatureSubState NewSubState);

	// ── Blueprint events ─────────────────────────────────────────────────────────

	UFUNCTION(BlueprintImplementableEvent, Category="Interactable")
	void BP_OnStateChanged(EInteractableState NewState);

	UFUNCTION(BlueprintImplementableEvent, Category="AI")
	void BP_OnSubStateChanged(ECreatureSubState NewSubState);

	UFUNCTION(BlueprintImplementableEvent, Category="Combat")
	void BP_OnDeath(AActor* Killer);

	// ── Components ───────────────────────────────────────────────────────────────

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interactable")
	UHMVRInteractableComponent* Interactable;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="AI")
	USphereComponent* DetectionSphere;

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnDetectionOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor,
	                             UPrimitiveComponent* OtherComp, int32 OtherBodyIndex,
	                             bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void OnDetectionOverlapEnd(UPrimitiveComponent* OverlappedComp, AActor* OtherActor,
	                           UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

	UFUNCTION()
	void OnInteractableStateChanged(EInteractableState NewState);
};
