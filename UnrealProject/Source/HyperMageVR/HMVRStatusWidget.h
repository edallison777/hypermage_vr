// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HMVRStatusWidget.generated.h"

class UTextBlock;
class UButton;
class UHorizontalBox;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStatusAction);

/**
 * Self-contained C++ status widget for matchmaking / connection UI.
 *
 * Builds its own UMG layout in NativeConstruct() — no Blueprint subclass or editor setup needed.
 * GameInstance calls Show*/HideWidget; Retry/Cancel buttons broadcast the assignable delegates.
 * Blueprint subclasses may override the Show*/HideWidget events if custom visuals are wanted.
 */
UCLASS(Blueprintable)
class HYPERMAGEVR_API UHMVRStatusWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** Show "Searching for match..." state. */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Status")
	void ShowSearching();
	virtual void ShowSearching_Implementation();

	/** Show "Match found — connecting..." state. */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Status")
	void ShowConnecting();
	virtual void ShowConnecting_Implementation();

	/** Show error message with Retry / Cancel buttons. */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Status")
	void ShowError(const FString& Message);
	virtual void ShowError_Implementation(const FString& Message);

	/** Show brief success confirmation before scene transition. */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Status")
	void ShowSuccess();
	virtual void ShowSuccess_Implementation();

	/** Hide the widget entirely. */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Status")
	void HideWidget();
	virtual void HideWidget_Implementation();

	/** Broadcast by the Retry button click. */
	UPROPERTY(BlueprintAssignable, Category = "Status")
	FOnStatusAction OnRetryRequested;

	/** Broadcast by the Cancel button click. */
	UPROPERTY(BlueprintAssignable, Category = "Status")
	FOnStatusAction OnCancelRequested;

protected:
	virtual void NativeConstruct() override;

private:
	void BuildWidgetTree();

	UFUNCTION()
	void OnRetryClicked();

	UFUNCTION()
	void OnCancelClicked();

	UPROPERTY()
	UTextBlock* StatusText = nullptr;

	UPROPERTY()
	UButton* RetryButton = nullptr;

	UPROPERTY()
	UButton* CancelButton = nullptr;

	UPROPERTY()
	UHorizontalBox* ButtonRow = nullptr;
};
