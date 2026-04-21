// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRStatusWidget.h"
#include "Components/TextBlock.h"
#include "Components/Button.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/Border.h"
#include "Components/BorderSlot.h"

void UHMVRStatusWidget::NativeConstruct()
{
	Super::NativeConstruct();

	if (!WidgetTree->RootWidget)
	{
		BuildWidgetTree();
	}
}

void UHMVRStatusWidget::BuildWidgetTree()
{
	// Root: full-screen overlay
	UOverlay* Root = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), TEXT("Root"));
	WidgetTree->RootWidget = Root;

	// Semi-transparent dark background fills the overlay
	UBorder* Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
	Background->SetBrushColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.75f));

	UOverlaySlot* BgSlot = Root->AddChildToOverlay(Background);
	BgSlot->SetHorizontalAlignment(HAlign_Fill);
	BgSlot->SetVerticalAlignment(VAlign_Fill);

	// Centered vertical box
	UVerticalBox* VBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("VBox"));
	UBorderSlot* VBoxSlot = Cast<UBorderSlot>(Background->AddChild(VBox));
	if (VBoxSlot)
	{
		VBoxSlot->SetHorizontalAlignment(HAlign_Center);
		VBoxSlot->SetVerticalAlignment(VAlign_Center);
		VBoxSlot->SetPadding(FMargin(40.0f));
	}

	// Status text
	StatusText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("StatusText"));
	StatusText->SetColorAndOpacity(FSlateColor(FLinearColor::White));
	FSlateFontInfo FontInfo = StatusText->GetFont();
	FontInfo.Size = 24;
	StatusText->SetFont(FontInfo);

	UVerticalBoxSlot* TextSlot = VBox->AddChildToVerticalBox(StatusText);
	TextSlot->SetHorizontalAlignment(HAlign_Center);
	TextSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 24.0f));

	// Button row — only visible in error state
	ButtonRow = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("ButtonRow"));
	ButtonRow->SetVisibility(ESlateVisibility::Collapsed);

	UVerticalBoxSlot* BtnRowSlot = VBox->AddChildToVerticalBox(ButtonRow);
	BtnRowSlot->SetHorizontalAlignment(HAlign_Center);

	// Retry button
	RetryButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("RetryButton"));
	RetryButton->OnClicked.AddDynamic(this, &UHMVRStatusWidget::OnRetryClicked);

	UTextBlock* RetryLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("RetryLabel"));
	RetryLabel->SetText(FText::FromString(TEXT("Retry")));
	RetryButton->AddChild(RetryLabel);

	UHorizontalBoxSlot* RetrySlot = ButtonRow->AddChildToHorizontalBox(RetryButton);
	RetrySlot->SetPadding(FMargin(12.0f, 0.0f));

	// Cancel button
	CancelButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("CancelButton"));
	CancelButton->OnClicked.AddDynamic(this, &UHMVRStatusWidget::OnCancelClicked);

	UTextBlock* CancelLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("CancelLabel"));
	CancelLabel->SetText(FText::FromString(TEXT("Cancel")));
	CancelButton->AddChild(CancelLabel);

	UHorizontalBoxSlot* CancelSlot = ButtonRow->AddChildToHorizontalBox(CancelButton);
	CancelSlot->SetPadding(FMargin(12.0f, 0.0f));
}

// ── Show/Hide implementations ─────────────────────────────────────────────────

void UHMVRStatusWidget::ShowSearching_Implementation()
{
	SetVisibility(ESlateVisibility::Visible);
	if (StatusText) StatusText->SetText(FText::FromString(TEXT("Searching for match...")));
	if (ButtonRow)  ButtonRow->SetVisibility(ESlateVisibility::Collapsed);
}

void UHMVRStatusWidget::ShowConnecting_Implementation()
{
	SetVisibility(ESlateVisibility::Visible);
	if (StatusText) StatusText->SetText(FText::FromString(TEXT("Match found - connecting...")));
	if (ButtonRow)  ButtonRow->SetVisibility(ESlateVisibility::Collapsed);
}

void UHMVRStatusWidget::ShowError_Implementation(const FString& Message)
{
	SetVisibility(ESlateVisibility::Visible);
	if (StatusText) StatusText->SetText(FText::FromString(Message));
	if (ButtonRow)  ButtonRow->SetVisibility(ESlateVisibility::Visible);
}

void UHMVRStatusWidget::ShowSuccess_Implementation()
{
	SetVisibility(ESlateVisibility::Visible);
	if (StatusText) StatusText->SetText(FText::FromString(TEXT("Connected!")));
	if (ButtonRow)  ButtonRow->SetVisibility(ESlateVisibility::Collapsed);
}

void UHMVRStatusWidget::HideWidget_Implementation()
{
	SetVisibility(ESlateVisibility::Collapsed);
}

// ── Button handlers ───────────────────────────────────────────────────────────

void UHMVRStatusWidget::OnRetryClicked()
{
	OnRetryRequested.Broadcast();
}

void UHMVRStatusWidget::OnCancelClicked()
{
	OnCancelRequested.Broadcast();
}
