// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HMVRStatusWidget.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStatusAction);

/**
 * Base widget class for matchmaking / connection status UI.
 *
 * Visual implementation lives in Blueprint (set StatusWidgetClass on the GameInstance BP).
 * C++ GameInstance calls Show*/HideWidget; Blueprint fires OnRetryRequested/OnCancelRequested.
 */
UCLASS(Abstract, Blueprintable)
class HYPERMAGEVR_API UHMVRStatusWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** Show "Searching for match…" state. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Status")
	void ShowSearching();

	/** Show "Match found — connecting…" state. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Status")
	void ShowConnecting();

	/** Show error message with Retry / Cancel buttons. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Status")
	void ShowError(const FString& Message);

	/** Show brief success confirmation before scene transition. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Status")
	void ShowSuccess();

	/** Hide the widget entirely. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Status")
	void HideWidget();

	/** Blueprint fires this when the player taps Retry. */
	UPROPERTY(BlueprintAssignable, Category = "Status")
	FOnStatusAction OnRetryRequested;

	/** Blueprint fires this when the player taps Cancel. */
	UPROPERTY(BlueprintAssignable, Category = "Status")
	FOnStatusAction OnCancelRequested;
};
