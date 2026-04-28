// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "HMVRCreatureAIController.generated.h"

class UBehaviorTree;
class UBlackboardComponent;

UCLASS()
class HYPERMAGEVR_API AHMVRCreatureAIController : public AAIController
{
	GENERATED_BODY()

public:
	AHMVRCreatureAIController();

	static const FName BB_PatrolTarget;   // FVector blackboard key
	static const FName BB_ChaseTarget;    // UObject (APawn) blackboard key
	static const FName BB_AttackRadius;   // float blackboard key

	void SetPatrolTarget(FVector Location);
	void SetChaseTarget(APawn* Target);

protected:
	virtual void OnPossess(APawn* InPawn) override;
};
