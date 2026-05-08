// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRCreatureAIController.h"
#include "HMVRCreature.h"
#include "NavigationSystem.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Navigation/PathFollowingComponent.h"

AHMVRCreatureAIController::AHMVRCreatureAIController()
{
	bWantsPlayerState = false;
}

void AHMVRCreatureAIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);

	SpawnLocation = InPawn->GetActorLocation();

	// 0.5s tick — coarse enough to be cheap, fine enough for responsive chase
	GetWorldTimerManager().SetTimer(TickTimer, this,
		&AHMVRCreatureAIController::AITick, 0.5f, true);
}

void AHMVRCreatureAIController::OnUnPossess()
{
	GetWorldTimerManager().ClearTimer(TickTimer);
	Super::OnUnPossess();
}

void AHMVRCreatureAIController::SetChaseTarget(APawn* Target)
{
	ChaseTarget = Target;
}

void AHMVRCreatureAIController::ClearChaseTarget()
{
	ChaseTarget = nullptr;
	StopMovement();
}

void AHMVRCreatureAIController::AITick()
{
	AHMVRCreature* Creature = Cast<AHMVRCreature>(GetPawn());
	if (!Creature || !Creature->HasAuthority()) return;
	if (Creature->Interactable->GetState() == EInteractableState::Resolved) return;

	if (!ChaseTarget)
	{
		DoPatrol();
		return;
	}

	float Dist = FVector::Dist(Creature->GetActorLocation(), ChaseTarget->GetActorLocation());
	if (Dist <= Creature->AttackRadius)
		DoAttack();
	else
		DoChase();
}

void AHMVRCreatureAIController::DoPatrol()
{
	// Only issue a new move when the previous one finished (or never started)
	if (GetMoveStatus() == EPathFollowingStatus::Moving) return;

	AHMVRCreature* Creature = Cast<AHMVRCreature>(GetPawn());
	UNavigationSystemV1* NavSys = UNavigationSystemV1::GetCurrent(GetWorld());
	if (!NavSys || !Creature) return;

	FNavLocation NavLoc;
	if (NavSys->GetRandomReachablePointInRadius(SpawnLocation, Creature->DetectionRadius * 0.5f, NavLoc))
	{
		MoveToLocation(NavLoc.Location, 50.f);
	}
}

void AHMVRCreatureAIController::DoChase()
{
	if (ChaseTarget)
		MoveToActor(ChaseTarget, 200.f);
}

void AHMVRCreatureAIController::DoAttack()
{
	StopMovement();

	AHMVRCreature* Creature = Cast<AHMVRCreature>(GetPawn());
	if (!Creature || !ChaseTarget) return;

	// Face the target and deal damage directly
	FVector Dir = (ChaseTarget->GetActorLocation() - Creature->GetActorLocation()).GetSafeNormal();
	Creature->SetActorRotation(Dir.Rotation());

	UGameplayStatics::ApplyDamage(ChaseTarget, Creature->AttackDamage, this, Creature, nullptr);
}
