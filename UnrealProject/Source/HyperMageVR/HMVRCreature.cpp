// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRCreature.h"
#include "HMVRCreatureAIController.h"
#include "Components/SphereComponent.h"
#include "Net/UnrealNetwork.h"
#include "GameFramework/PlayerController.h"

AHMVRCreature::AHMVRCreature()
{
	bReplicates = true;
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	AIControllerClass = AHMVRCreatureAIController::StaticClass();

	Interactable = CreateDefaultSubobject<UHMVRInteractableComponent>(TEXT("Interactable"));

	DetectionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("DetectionSphere"));
	DetectionSphere->SetupAttachment(RootComponent);
	DetectionSphere->SetSphereRadius(DetectionRadius);
	DetectionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	DetectionSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	DetectionSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
}

void AHMVRCreature::BeginPlay()
{
	Super::BeginPlay();
	Health = MaxHealth;
	DetectionSphere->SetSphereRadius(DetectionRadius);
	DetectionSphere->OnComponentBeginOverlap.AddDynamic(this, &AHMVRCreature::OnDetectionOverlapBegin);
	DetectionSphere->OnComponentEndOverlap.AddDynamic(this, &AHMVRCreature::OnDetectionOverlapEnd);
	Interactable->OnStateChanged.AddDynamic(this, &AHMVRCreature::OnInteractableStateChanged);

	if (bReplicates && HasAuthority())
	{
		Interactable->LoadState();
	}
}

void AHMVRCreature::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AHMVRCreature, Health);
	DOREPLIFETIME(AHMVRCreature, CreatureSubState);
}

void AHMVRCreature::OnDetectionOverlapBegin(UPrimitiveComponent*, AActor* OtherActor,
                                             UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	if (!HasAuthority()) return;
	APlayerController* PC = Cast<APlayerController>(OtherActor->GetInstigatorController());
	if (!PC) return;

	float Dist = FVector::Dist(GetActorLocation(), OtherActor->GetActorLocation());
	OnPlayerApproach(PC, Dist);
}

void AHMVRCreature::OnDetectionOverlapEnd(UPrimitiveComponent*, AActor* OtherActor,
                                           UPrimitiveComponent*, int32)
{
	if (!HasAuthority()) return;
	// Return to patrol only if still alive
	if (Interactable->GetState() == EInteractableState::Alert)
	{
		Interactable->TransitionTo(EInteractableState::Idle);
		SetCreatureSubState(ECreatureSubState::Patrol);
	}
}

void AHMVRCreature::OnPlayerApproach(APlayerController* Player, float Distance)
{
	if (!HasAuthority()) return;
	if (Interactable->GetState() == EInteractableState::Resolved) return;

	Interactable->TransitionTo(EInteractableState::Alert);
	SetCreatureSubState(Distance <= AttackRadius ? ECreatureSubState::Attack : ECreatureSubState::Chase);

	if (AHMVRCreatureAIController* AI = Cast<AHMVRCreatureAIController>(GetController()))
	{
		AI->SetChaseTarget(Player->GetPawn());
	}
}

void AHMVRCreature::OnPlayerInteract(APlayerController* Player)
{
	// Interacting with a creature triggers an attack from the creature's side
	OnPlayerApproach(Player, FVector::Dist(GetActorLocation(), Player->GetPawn()->GetActorLocation()));
}

void AHMVRCreature::OnDamageReceived(float Amount, AActor* Source)
{
	if (!HasAuthority()) return;
	if (Interactable->GetState() == EInteractableState::Resolved) return;

	Health = FMath::Max(0.f, Health - Amount);
	Interactable->TransitionTo(EInteractableState::Active);
	SetCreatureSubState(ECreatureSubState::Attack);

	if (Health <= 0.f)
	{
		Interactable->TransitionTo(EInteractableState::Resolved);
		BP_OnDeath(Source);
	}
}

float AHMVRCreature::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent,
                                  AController* EventInstigator, AActor* DamageCauser)
{
	float Actual = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	OnDamageReceived(Actual, DamageCauser);
	return Actual;
}

void AHMVRCreature::SetCreatureSubState(ECreatureSubState NewSubState)
{
	if (CreatureSubState == NewSubState) return;
	CreatureSubState = NewSubState;
	BP_OnSubStateChanged(NewSubState);
}

void AHMVRCreature::OnInteractableStateChanged(EInteractableState NewState)
{
	BP_OnStateChanged(NewState);
}
