// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRArtifact.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SphereComponent.h"
#include "GameFramework/RotatingMovementComponent.h"

AHMVRArtifact::AHMVRArtifact()
{
	bReplicates = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

	PickupSphere = CreateDefaultSubobject<USphereComponent>(TEXT("PickupSphere"));
	PickupSphere->SetupAttachment(RootComponent);
	PickupSphere->SetSphereRadius(100.f);
	PickupSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PickupSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	PickupSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	RotatingMovement = CreateDefaultSubobject<URotatingMovementComponent>(TEXT("RotatingMovement"));
	RotatingMovement->RotationRate = FRotator(0.f, 45.f, 0.f);

	Interactable = CreateDefaultSubobject<UHMVRInteractableComponent>(TEXT("Interactable"));
}

void AHMVRArtifact::BeginPlay()
{
	Super::BeginPlay();
	RotatingMovement->SetActive(bRotates);
	Interactable->OnStateChanged.AddDynamic(this, &AHMVRArtifact::OnInteractableStateChanged);

	if (HasAuthority())
	{
		Interactable->LoadState();
	}
}

void AHMVRArtifact::OnPlayerApproach(APlayerController* Player, float Distance)
{
	if (!HasAuthority()) return;
	if (Interactable->GetState() == EInteractableState::Resolved) return;
	Interactable->TransitionTo(EInteractableState::Alert);
}

void AHMVRArtifact::OnPlayerInteract(APlayerController* Player)
{
	OnCollected(Player);
}

void AHMVRArtifact::OnCollected(APlayerController* Player)
{
	if (!HasAuthority()) return;
	if (Interactable->GetState() == EInteractableState::Resolved) return;

	Interactable->TransitionTo(EInteractableState::Resolved);
	SetActorHiddenInGame(true);
	SetActorEnableCollision(false);

	OnArtifactCollected.Broadcast(this, Player);
	BP_OnCollected(Player);
}

void AHMVRArtifact::OnInteractableStateChanged(EInteractableState NewState)
{
	BP_OnStateChanged(NewState);
}
