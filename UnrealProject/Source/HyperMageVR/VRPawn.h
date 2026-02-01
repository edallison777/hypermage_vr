// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "InputActionValue.h"
#include "VRPawn.generated.h"

class UCameraComponent;
class UMotionControllerComponent;
class UInputMappingContext;
class UInputAction;
class UPostProcessComponent;

/**
 * VR comfort settings for motion sickness reduction
 */
UENUM(BlueprintType)
enum class EVRLocomotionMode : uint8
{
	SmoothLocomotion UMETA(DisplayName = "Smooth Locomotion"),
	Teleport UMETA(DisplayName = "Teleport"),
	Flight UMETA(DisplayName = "Flight (Optional)")
};

UENUM(BlueprintType)
enum class EVRRotationMode : uint8
{
	SnapTurn UMETA(DisplayName = "Snap Turn"),
	SmoothTurn UMETA(DisplayName = "Smooth Turn")
};

/**
 * VR Pawn with comfort settings for Meta Quest 3
 * Implements Requirements 1.3-1.7: Smooth locomotion, snap turn, comfort vignette, teleport, flight
 */
UCLASS()
class HYPERMAGEVR_API AVRPawn : public APawn
{
	GENERATED_BODY()

public:
	AVRPawn();

protected:
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
	virtual void Tick(float DeltaTime) override;

	// Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
	TObjectPtr<UCameraComponent> VRCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
	TObjectPtr<USceneComponent> VROrigin;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
	TObjectPtr<UMotionControllerComponent> LeftController;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
	TObjectPtr<UMotionControllerComponent> RightController;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "VR")
	TObjectPtr<UPostProcessComponent> ComfortVignettePostProcess;

	// Enhanced Input
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> VRMappingContext;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> TurnAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> TeleportAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> FlightAction;

	// Comfort Settings
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort", Replicated)
	EVRLocomotionMode LocomotionMode = EVRLocomotionMode::SmoothLocomotion;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort", Replicated)
	EVRRotationMode RotationMode = EVRRotationMode::SnapTurn;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort", Replicated)
	bool bComfortVignetteEnabled = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort", Replicated)
	bool bFlightModeEnabled = false;

	// Locomotion Parameters
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Locomotion")
	float SmoothLocomotionSpeed = 300.0f; // cm/s

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Locomotion")
	float FlightSpeed = 500.0f; // cm/s

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Locomotion")
	float TeleportMaxDistance = 1000.0f; // cm

	// Rotation Parameters
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Rotation")
	float SnapTurnAngle = 45.0f; // degrees

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Rotation")
	float SmoothTurnSpeed = 90.0f; // degrees/s

	// Comfort Vignette Parameters
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort")
	float VignetteIntensity = 0.7f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort")
	float VignetteFadeSpeed = 2.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VR|Comfort")
	float AccelerationThreshold = 100.0f; // cm/s^2

private:
	// Input Handlers
	void HandleMove(const FInputActionValue& Value);
	void HandleTurn(const FInputActionValue& Value);
	void HandleTeleport(const FInputActionValue& Value);
	void HandleFlight(const FInputActionValue& Value);

	// Locomotion Implementation
	void ApplySmoothLocomotion(const FVector2D& Input, float DeltaTime);
	void ApplyTeleport(const FVector2D& Input);
	void ApplyFlight(const FVector2D& Input, float DeltaTime);

	// Rotation Implementation
	void ApplySnapTurn(float Input);
	void ApplySmoothTurn(float Input, float DeltaTime);

	// Comfort Vignette
	void UpdateComfortVignette(float DeltaTime);
	float CalculateVignetteAmount() const;

	// State
	FVector LastVelocity;
	float CurrentVignetteAmount = 0.0f;
	bool bIsTeleporting = false;
	bool bSnapTurnCooldown = false;
	float SnapTurnCooldownTimer = 0.0f;
	const float SnapTurnCooldownDuration = 0.3f;

	// Replication
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// Server RPCs for movement validation
	UFUNCTION(Server, Reliable, WithValidation)
	void ServerMove(FVector NewLocation, FRotator NewRotation, float Timestamp);

	UFUNCTION(Server, Reliable, WithValidation)
	void ServerTeleport(FVector TargetLocation, float Timestamp);
};
