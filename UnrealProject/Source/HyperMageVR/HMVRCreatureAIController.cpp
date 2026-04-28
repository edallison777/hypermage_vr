// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRCreatureAIController.h"
#include "HMVRCreature.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BlackboardComponent.h"

const FName AHMVRCreatureAIController::BB_PatrolTarget  = TEXT("PatrolTarget");
const FName AHMVRCreatureAIController::BB_ChaseTarget   = TEXT("ChaseTarget");
const FName AHMVRCreatureAIController::BB_AttackRadius  = TEXT("AttackRadius");

AHMVRCreatureAIController::AHMVRCreatureAIController()
{
	bWantsPlayerState = false;
}

void AHMVRCreatureAIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);

	AHMVRCreature* Creature = Cast<AHMVRCreature>(InPawn);
	if (!Creature || !Creature->BehaviorTreeAsset) return;

	UBlackboardData* BBAsset = Creature->BehaviorTreeAsset->BlackboardAsset;
	if (UseBlackboard(BBAsset, Blackboard))
	{
		Blackboard->SetValueAsFloat(BB_AttackRadius, Creature->AttackRadius);
		RunBehaviorTree(Creature->BehaviorTreeAsset);
	}
}

void AHMVRCreatureAIController::SetPatrolTarget(FVector Location)
{
	if (Blackboard)
	{
		Blackboard->SetValueAsVector(BB_PatrolTarget, Location);
	}
}

void AHMVRCreatureAIController::SetChaseTarget(APawn* Target)
{
	if (Blackboard)
	{
		Blackboard->SetValueAsObject(BB_ChaseTarget, Target);
	}
}
