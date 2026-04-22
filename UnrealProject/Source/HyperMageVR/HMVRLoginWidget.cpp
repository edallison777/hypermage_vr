// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRLoginWidget.h"
#include "HMVRGameInstance.h"
#include "Blueprint/WidgetTree.h"
#include "Components/TextBlock.h"
#include "Components/Button.h"
#include "Components/EditableTextBox.h"
#include "Components/EditableText.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/Border.h"
#include "Components/BorderSlot.h"

void UHMVRLoginWidget::NativeConstruct()
{
	Super::NativeConstruct();

	if (!WidgetTree->RootWidget)
	{
		BuildWidgetTree();
	}

	if (UHMVRGameInstance* GI = Cast<UHMVRGameInstance>(GetGameInstance()))
	{
		GI->OnLoginResult.AddDynamic(this, &UHMVRLoginWidget::OnLoginResult);
	}
}

void UHMVRLoginWidget::NativeDestruct()
{
	if (UHMVRGameInstance* GI = Cast<UHMVRGameInstance>(GetGameInstance()))
	{
		GI->OnLoginResult.RemoveDynamic(this, &UHMVRLoginWidget::OnLoginResult);
	}
	Super::NativeDestruct();
}

void UHMVRLoginWidget::BuildWidgetTree()
{
	UOverlay* Root = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), TEXT("Root"));
	WidgetTree->RootWidget = Root;

	UBorder* Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
	Background->SetBrushColor(FLinearColor(0.05f, 0.05f, 0.1f, 1.0f));
	UOverlaySlot* BgSlot = Root->AddChildToOverlay(Background);
	BgSlot->SetHorizontalAlignment(HAlign_Fill);
	BgSlot->SetVerticalAlignment(VAlign_Fill);

	UVerticalBox* VBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("VBox"));
	UBorderSlot* VBoxSlot = Cast<UBorderSlot>(Background->AddChild(VBox));
	if (VBoxSlot)
	{
		VBoxSlot->SetHorizontalAlignment(HAlign_Center);
		VBoxSlot->SetVerticalAlignment(VAlign_Center);
		VBoxSlot->SetPadding(FMargin(80.0f));
	}

	// Title
	UTextBlock* Title = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Title"));
	Title->SetText(FText::FromString(TEXT("HyperMage VR")));
	Title->SetColorAndOpacity(FSlateColor(FLinearColor(0.4f, 0.8f, 1.0f)));
	FSlateFontInfo TitleFont = Title->GetFont();
	TitleFont.Size = 36;
	Title->SetFont(TitleFont);
	UVerticalBoxSlot* TitleSlot = VBox->AddChildToVerticalBox(Title);
	TitleSlot->SetHorizontalAlignment(HAlign_Center);
	TitleSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 48.0f));

	// Username
	UsernameField = WidgetTree->ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass(), TEXT("Username"));
	UsernameField->SetHintText(FText::FromString(TEXT("Username")));
	UVerticalBoxSlot* UserSlot = VBox->AddChildToVerticalBox(UsernameField);
	UserSlot->SetHorizontalAlignment(HAlign_Fill);
	UserSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 16.0f));

	// Password (UEditableText supports bIsPassword; UEditableTextBox dropped it in UE5.6)
	PasswordField = WidgetTree->ConstructWidget<UEditableText>(UEditableText::StaticClass(), TEXT("Password"));
	PasswordField->SetHintText(FText::FromString(TEXT("Password")));
	PasswordField->SetIsPassword(true);
	UVerticalBoxSlot* PassSlot = VBox->AddChildToVerticalBox(PasswordField);
	PassSlot->SetHorizontalAlignment(HAlign_Fill);
	PassSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 32.0f));

	// Login button
	LoginButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("LoginButton"));
	LoginButton->OnClicked.AddDynamic(this, &UHMVRLoginWidget::OnLoginClicked);
	UTextBlock* BtnLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("LoginLabel"));
	BtnLabel->SetText(FText::FromString(TEXT("LOGIN")));
	LoginButton->AddChild(BtnLabel);
	UVerticalBoxSlot* BtnSlot = VBox->AddChildToVerticalBox(LoginButton);
	BtnSlot->SetHorizontalAlignment(HAlign_Fill);
	BtnSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 16.0f));

	// Status / error label
	StatusLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Status"));
	StatusLabel->SetColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.35f, 0.35f)));
	StatusLabel->SetText(FText::GetEmpty());
	FSlateFontInfo StatusFont = StatusLabel->GetFont();
	StatusFont.Size = 16;
	StatusLabel->SetFont(StatusFont);
	UVerticalBoxSlot* StatusSlot = VBox->AddChildToVerticalBox(StatusLabel);
	StatusSlot->SetHorizontalAlignment(HAlign_Center);
}

void UHMVRLoginWidget::ShowError(const FString& Message)
{
	if (StatusLabel) StatusLabel->SetText(FText::FromString(Message));
	if (LoginButton)  LoginButton->SetIsEnabled(true);
}

void UHMVRLoginWidget::OnLoginClicked()
{
	if (!UsernameField || !PasswordField || !LoginButton) return;

	const FString Username = UsernameField->GetText().ToString().TrimStartAndEnd();
	const FString Password = PasswordField->GetText().ToString();

	if (Username.IsEmpty() || Password.IsEmpty())
	{
		ShowError(TEXT("Please enter username and password"));
		return;
	}

	if (StatusLabel) StatusLabel->SetText(FText::FromString(TEXT("Logging in...")));
	LoginButton->SetIsEnabled(false);

	if (UHMVRGameInstance* GI = Cast<UHMVRGameInstance>(GetGameInstance()))
	{
		GI->Login(Username, Password);
	}
}

void UHMVRLoginWidget::OnLoginResult(bool bSuccess, const FString& ErrorMessage)
{
	if (bSuccess)
	{
		SetVisibility(ESlateVisibility::Collapsed);
	}
	else
	{
		ShowError(ErrorMessage.IsEmpty() ? TEXT("Login failed — please try again") : ErrorMessage);
	}
}
