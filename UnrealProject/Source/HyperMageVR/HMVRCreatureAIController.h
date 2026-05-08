// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "HMVRCreatureAIController.generated.h"

UCLASS()
class HYPERMAGEVR_API AHMVRCreatureAIController : public AAIController
{
	GENERATED_BODY()

public:
	AHMVRCreatureAIController();

	void SetChaseTarget(APawn* Target);
	void ClearChaseTarget();

protected:
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;

private:
	UPROPERTY()
	APawn* ChaseTarget = nullptr;

	FVector SpawnLocation;
	FTimerHandle TickTimer;

	void AITick();
	void DoPatrol();
	void DoChase();
	void DoAttack();
};
