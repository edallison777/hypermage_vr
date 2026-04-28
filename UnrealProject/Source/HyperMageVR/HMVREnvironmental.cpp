// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVREnvironmental.h"
#include "Components/SphereComponent.h"
#include "GameFramework/PlayerController.h"

AHMVREnvironmental::AHMVREnvironmental()
{
	bReplicates = true;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	TriggerSphere = CreateDefaultSubobject<USphereComponent>(TEXT("TriggerSphere"));
	TriggerSphere->SetupAttachment(RootComponent);
	TriggerSphere->SetSphereRadius(TriggerRadius);
	TriggerSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	TriggerSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	TriggerSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	Interactable = CreateDefaultSubobject<UHMVRInteractableComponent>(TEXT("Interactable"));
}

void AHMVREnvironmental::BeginPlay()
{
	Super::BeginPlay();
	TriggerSphere->SetSphereRadius(TriggerRadius);
	TriggerSphere->SetCollisionEnabled(bAutoTrigger ? ECollisionEnabled::QueryOnly
	                                                : ECollisionEnabled::NoCollision);

	if (bAutoTrigger)
	{
		TriggerSphere->OnComponentBeginOverlap.AddDynamic(this, &AHMVREnvironmental::OnTriggerOverlapBegin);
	}

	Interactable->OnStateChanged.AddDynamic(this, &AHMVREnvironmental::OnInteractableStateChanged);

	if (HasAuthority())
	{
		Interactable->LoadState();
	}
}

void AHMVREnvironmental::OnTriggerOverlapBegin(UPrimitiveComponent*, AActor* OtherActor,
                                                UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	if (!HasAuthority()) return;
	if (Cast<APawn>(OtherActor))
	{
		Trigger(OtherActor);
	}
}

void AHMVREnvironmental::OnPlayerApproach(APlayerController* Player, float Distance)
{
	Trigger(Player);
}

void AHMVREnvironmental::OnPlayerInteract(APlayerController* Player)
{
	Trigger(Player);
}

void AHMVREnvironmental::Trigger(AActor* Instigator)
{
	if (!HasAuthority()) return;
	if (bOneShot && bTriggered) return;
	if (Interactable->GetState() == EInteractableState::Resolved) return;

	bTriggered = true;
	Interactable->TransitionTo(EInteractableState::Active);
	BP_OnTriggered(Instigator);

	GetWorldTimerManager().SetTimer(SequenceTimerHandle, this,
	                                &AHMVREnvironmental::OnSequenceComplete,
	                                EventSequenceDuration, false);
}

void AHMVREnvironmental::OnSequenceComplete()
{
	Interactable->TransitionTo(EInteractableState::Resolved);
	BP_OnResolved();
}

void AHMVREnvironmental::OnInteractableStateChanged(EInteractableState NewState)
{
	BP_OnStateChanged(NewState);
}
