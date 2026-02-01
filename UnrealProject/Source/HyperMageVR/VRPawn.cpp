// Copyright 2026 HyperMage. All Rights Reserved.

#include "VRPawn.h"
#include "Camera/CameraComponent.h"
#include "MotionControllerComponent.h"
#include "Components/PostProcessComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Net/UnrealNetwork.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "DrawDebugHelpers.h"

AVRPawn::AVRPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	SetReplicateMovement(true);

	// Create VR Origin (root component for VR tracking space)
	VROrigin = CreateDefaultSubobject<USceneComponent>(TEXT("VROrigin"));
	RootComponent = VROrigin;

	// Create VR Camera
	VRCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("VRCamera"));
	VRCamera->SetupAttachment(VROrigin);
	VRCamera->bUsePawnControlRotation = false;

	// Create Motion Controllers
	LeftController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("LeftController"));
	LeftController->SetupAttachment(VROrigin);
	LeftController->MotionSource = FName("Left");

	RightController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("RightController"));
	RightController->SetupAttachment(VROrigin);
	RightController->MotionSource = FName("Right");

	// Create Comfort Vignette Post Process
	ComfortVignettePostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("ComfortVignette"));
	ComfortVignettePostProcess->SetupAttachment(VRCamera);
	ComfortVignettePostProcess->bEnabled = true;
	ComfortVignettePostProcess->bUnbound = true;
}

void AVRPawn::BeginPlay()
{
	Super::BeginPlay();

	// Setup Enhanced Input
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = 
			ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			if (VRMappingContext)
			{
				Subsystem->AddMappingContext(VRMappingContext, 0);
			}
		}
	}

	// Initialize comfort vignette
	if (bComfortVignetteEnabled)
	{
		ComfortVignettePostProcess->bEnabled = true;
	}
	else
	{
		ComfortVignettePostProcess->bEnabled = false;
	}
}

void AVRPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		// Bind movement
		if (MoveAction)
		{
			EnhancedInput->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AVRPawn::HandleMove);
		}

		// Bind turning
		if (TurnAction)
		{
			EnhancedInput->BindAction(TurnAction, ETriggerEvent::Triggered, this, &AVRPawn::HandleTurn);
		}

		// Bind teleport
		if (TeleportAction)
		{
			EnhancedInput->BindAction(TeleportAction, ETriggerEvent::Started, this, &AVRPawn::HandleTeleport);
		}

		// Bind flight (if enabled)
		if (FlightAction && bFlightModeEnabled)
		{
			EnhancedInput->BindAction(FlightAction, ETriggerEvent::Triggered, this, &AVRPawn::HandleFlight);
		}
	}
}

void AVRPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// Update comfort vignette based on movement
	if (bComfortVignetteEnabled)
	{
		UpdateComfortVignette(DeltaTime);
	}

	// Update snap turn cooldown
	if (bSnapTurnCooldown)
	{
		SnapTurnCooldownTimer -= DeltaTime;
		if (SnapTurnCooldownTimer <= 0.0f)
		{
			bSnapTurnCooldown = false;
		}
	}
}

void AVRPawn::HandleMove(const FInputActionValue& Value)
{
	const FVector2D MovementVector = Value.Get<FVector2D>();

	if (MovementVector.IsNearlyZero())
	{
		return;
	}

	switch (LocomotionMode)
	{
	case EVRLocomotionMode::SmoothLocomotion:
		ApplySmoothLocomotion(MovementVector, GetWorld()->GetDeltaSeconds());
		break;
	case EVRLocomotionMode::Teleport:
		// Teleport is handled by separate action
		break;
	case EVRLocomotionMode::Flight:
		if (bFlightModeEnabled)
		{
			ApplyFlight(MovementVector, GetWorld()->GetDeltaSeconds());
		}
		break;
	}
}

void AVRPawn::HandleTurn(const FInputActionValue& Value)
{
	const float TurnValue = Value.Get<float>();

	if (FMath::IsNearlyZero(TurnValue))
	{
		return;
	}

	switch (RotationMode)
	{
	case EVRRotationMode::SnapTurn:
		ApplySnapTurn(TurnValue);
		break;
	case EVRRotationMode::SmoothTurn:
		ApplySmoothTurn(TurnValue, GetWorld()->GetDeltaSeconds());
		break;
	}
}

void AVRPawn::HandleTeleport(const FInputActionValue& Value)
{
	if (LocomotionMode != EVRLocomotionMode::Teleport)
	{
		return;
	}

	const FVector2D TeleportInput = Value.Get<FVector2D>();
	ApplyTeleport(TeleportInput);
}

void AVRPawn::HandleFlight(const FInputActionValue& Value)
{
	if (!bFlightModeEnabled || LocomotionMode != EVRLocomotionMode::Flight)
	{
		return;
	}

	const FVector2D FlightInput = Value.Get<FVector2D>();
	ApplyFlight(FlightInput, GetWorld()->GetDeltaSeconds());
}

void AVRPawn::ApplySmoothLocomotion(const FVector2D& Input, float DeltaTime)
{
	if (!VRCamera)
	{
		return;
	}

	// Get camera forward and right vectors (projected to horizontal plane)
	FVector Forward = VRCamera->GetForwardVector();
	Forward.Z = 0.0f;
	Forward.Normalize();

	FVector Right = VRCamera->GetRightVector();
	Right.Z = 0.0f;
	Right.Normalize();

	// Calculate movement direction
	FVector MovementDirection = (Forward * Input.Y + Right * Input.X).GetSafeNormal();
	FVector NewLocation = GetActorLocation() + MovementDirection * SmoothLocomotionSpeed * DeltaTime;

	// Server validation for movement
	if (HasAuthority())
	{
		SetActorLocation(NewLocation);
	}
	else
	{
		// Client prediction
		SetActorLocation(NewLocation);
		ServerMove(NewLocation, GetActorRotation(), GetWorld()->GetTimeSeconds());
	}
}

void AVRPawn::ApplyTeleport(const FVector2D& Input)
{
	if (!VRCamera || bIsTeleporting)
	{
		return;
	}

	// Calculate teleport target location
	FVector CameraForward = VRCamera->GetForwardVector();
	CameraForward.Z = 0.0f;
	CameraForward.Normalize();

	FVector TargetLocation = GetActorLocation() + CameraForward * TeleportMaxDistance;

	// Perform line trace to find valid teleport location
	FHitResult HitResult;
	FVector TraceStart = TargetLocation + FVector(0, 0, 100);
	FVector TraceEnd = TargetLocation - FVector(0, 0, 500);

	FCollisionQueryParams QueryParams;
	QueryParams.AddIgnoredActor(this);

	if (GetWorld()->LineTraceSingleByChannel(HitResult, TraceStart, TraceEnd, ECC_Visibility, QueryParams))
	{
		TargetLocation = HitResult.Location;
	}

	// Server validation for teleport
	if (HasAuthority())
	{
		SetActorLocation(TargetLocation);
	}
	else
	{
		ServerTeleport(TargetLocation, GetWorld()->GetTimeSeconds());
	}

	bIsTeleporting = true;
	
	// Reset teleport flag after a short delay
	FTimerHandle TeleportTimerHandle;
	GetWorld()->GetTimerManager().SetTimer(TeleportTimerHandle, [this]()
	{
		bIsTeleporting = false;
	}, 0.5f, false);
}

void AVRPawn::ApplyFlight(const FVector2D& Input, float DeltaTime)
{
	if (!VRCamera)
	{
		return;
	}

	// Get camera forward and right vectors (including vertical component for flight)
	FVector Forward = VRCamera->GetForwardVector();
	FVector Right = VRCamera->GetRightVector();

	// Calculate movement direction
	FVector MovementDirection = (Forward * Input.Y + Right * Input.X).GetSafeNormal();
	FVector NewLocation = GetActorLocation() + MovementDirection * FlightSpeed * DeltaTime;

	// Server validation for movement
	if (HasAuthority())
	{
		SetActorLocation(NewLocation);
	}
	else
	{
		SetActorLocation(NewLocation);
		ServerMove(NewLocation, GetActorRotation(), GetWorld()->GetTimeSeconds());
	}
}

void AVRPawn::ApplySnapTurn(float Input)
{
	if (bSnapTurnCooldown || FMath::IsNearlyZero(Input, 0.5f))
	{
		return;
	}

	// Determine turn direction
	float TurnAngle = Input > 0 ? SnapTurnAngle : -SnapTurnAngle;

	// Apply rotation
	FRotator NewRotation = GetActorRotation();
	NewRotation.Yaw += TurnAngle;

	if (HasAuthority())
	{
		SetActorRotation(NewRotation);
	}
	else
	{
		SetActorRotation(NewRotation);
		ServerMove(GetActorLocation(), NewRotation, GetWorld()->GetTimeSeconds());
	}

	// Start cooldown
	bSnapTurnCooldown = true;
	SnapTurnCooldownTimer = SnapTurnCooldownDuration;
}

void AVRPawn::ApplySmoothTurn(float Input, float DeltaTime)
{
	if (FMath::IsNearlyZero(Input))
	{
		return;
	}

	// Apply smooth rotation
	FRotator NewRotation = GetActorRotation();
	NewRotation.Yaw += Input * SmoothTurnSpeed * DeltaTime;

	if (HasAuthority())
	{
		SetActorRotation(NewRotation);
	}
	else
	{
		SetActorRotation(NewRotation);
		ServerMove(GetActorLocation(), NewRotation, GetWorld()->GetTimeSeconds());
	}
}

void AVRPawn::UpdateComfortVignette(float DeltaTime)
{
	float TargetVignetteAmount = CalculateVignetteAmount();

	// Smoothly interpolate vignette intensity
	CurrentVignetteAmount = FMath::FInterpTo(
		CurrentVignetteAmount, 
		TargetVignetteAmount, 
		DeltaTime, 
		VignetteFadeSpeed
	);

	// Update post process material parameter
	// Note: This requires a post process material with a "VignetteAmount" parameter
	if (ComfortVignettePostProcess && ComfortVignettePostProcess->bEnabled)
	{
		// Material parameter update would go here
		// ComfortVignettePostProcess->Settings.WeightedBlendables.Array[0].Weight = CurrentVignetteAmount;
	}
}

float AVRPawn::CalculateVignetteAmount() const
{
	// Calculate acceleration
	FVector CurrentVelocity = GetVelocity();
	FVector Acceleration = (CurrentVelocity - LastVelocity) / GetWorld()->GetDeltaSeconds();
	float AccelerationMagnitude = Acceleration.Size();

	// Calculate vignette amount based on acceleration
	if (AccelerationMagnitude > AccelerationThreshold)
	{
		float ExcessAcceleration = AccelerationMagnitude - AccelerationThreshold;
		float VignetteAmount = FMath::Clamp(ExcessAcceleration / 500.0f, 0.0f, VignetteIntensity);
		return VignetteAmount;
	}

	return 0.0f;
}

void AVRPawn::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	DOREPLIFETIME(AVRPawn, LocomotionMode);
	DOREPLIFETIME(AVRPawn, RotationMode);
	DOREPLIFETIME(AVRPawn, bComfortVignetteEnabled);
	DOREPLIFETIME(AVRPawn, bFlightModeEnabled);
}

void AVRPawn::ServerMove_Implementation(FVector NewLocation, FRotator NewRotation, float Timestamp)
{
	// Server-side validation of movement
	// Check for cheating, impossible movements, etc.
	
	// For now, accept the movement (full validation would check distance, speed, etc.)
	SetActorLocation(NewLocation);
	SetActorRotation(NewRotation);
}

bool AVRPawn::ServerMove_Validate(FVector NewLocation, FRotator NewRotation, float Timestamp)
{
	// Validate movement is reasonable
	float Distance = FVector::Dist(GetActorLocation(), NewLocation);
	float MaxDistance = SmoothLocomotionSpeed * 0.1f; // Max distance per frame at 10fps

	return Distance <= MaxDistance;
}

void AVRPawn::ServerTeleport_Implementation(FVector TargetLocation, float Timestamp)
{
	// Server-side validation of teleport
	float Distance = FVector::Dist(GetActorLocation(), TargetLocation);
	
	if (Distance <= TeleportMaxDistance * 1.1f) // Allow 10% tolerance
	{
		SetActorLocation(TargetLocation);
	}
}

bool AVRPawn::ServerTeleport_Validate(FVector TargetLocation, float Timestamp)
{
	// Validate teleport distance
	float Distance = FVector::Dist(GetActorLocation(), TargetLocation);
	return Distance <= TeleportMaxDistance * 1.1f;
}
