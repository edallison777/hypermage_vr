// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRMachinery.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Net/UnrealNetwork.h"

AHMVRMachinery::AHMVRMachinery()
{
	bReplicates = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);

	InteractionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("InteractionSphere"));
	InteractionSphere->SetupAttachment(RootComponent);
	InteractionSphere->SetSphereRadius(150.f);
	InteractionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	InteractionSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	InteractionSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	Interactable = CreateDefaultSubobject<UHMVRInteractableComponent>(TEXT("Interactable"));
}

void AHMVRMachinery::BeginPlay()
{
	Super::BeginPlay();
	Interactable->OnStateChanged.AddDynamic(this, &AHMVRMachinery::OnInteractableStateChanged);

	if (HasAuthority())
	{
		Interactable->LoadState();
	}
}

void AHMVRMachinery::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AHMVRMachinery, MachinerySubState);
}

void AHMVRMachinery::OnPlayerApproach(APlayerController* Player, float Distance)
{
	if (!HasAuthority()) return;
	if (MachinerySubState != EMachinerySubState::Locked) return;
	Interactable->TransitionTo(EInteractableState::Alert);
}

void AHMVRMachinery::OnPlayerInteract(APlayerController* Player)
{
	if (!HasAuthority()) return;
	if (MachinerySubState != EMachinerySubState::Locked) return;

	// Key check: caller is responsible for passing interact only when key conditions are met.
	// Inventory system will enforce bRequiresKey / RequiredKeyId before calling this.

	MachinerySubState = EMachinerySubState::Unlocking;
	Interactable->TransitionTo(EInteractableState::Active);
	BP_OnTriggered();

	GetWorldTimerManager().SetTimer(UnlockTimerHandle, this,
	                                &AHMVRMachinery::OnUnlockTimerComplete,
	                                TriggerDelay, false);
}

void AHMVRMachinery::OnUnlockTimerComplete()
{
	MachinerySubState = EMachinerySubState::Open;
	Interactable->TransitionTo(EInteractableState::Resolved);
	BP_OnOpened();
}

void AHMVRMachinery::OnInteractableStateChanged(EInteractableState NewState)
{
	BP_OnStateChanged(NewState);
}
