// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HMVRLoginWidget.generated.h"

class UTextBlock;
class UButton;
class UEditableTextBox;
class UEditableText;

/**
 * Self-contained C++ login widget. Builds its own UMG layout in NativeConstruct() —
 * no Blueprint subclass or editor setup needed. Calls GameInstance::Login() on submit
 * and listens to GameInstance::OnLoginResult to show errors or dismiss itself.
 */
UCLASS()
class HYPERMAGEVR_API UHMVRLoginWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void ShowError(const FString& Message);

protected:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;

private:
	void BuildWidgetTree();

	UFUNCTION()
	void OnLoginClicked();

	UFUNCTION()
	void OnLoginResult(bool bSuccess, const FString& ErrorMessage);

	UPROPERTY()
	UEditableTextBox* UsernameField = nullptr;

	UPROPERTY()
	UEditableText* PasswordField = nullptr;

	UPROPERTY()
	UButton* LoginButton = nullptr;

	UPROPERTY()
	UTextBlock* StatusLabel = nullptr;
};
