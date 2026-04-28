// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRInteractableComponent.h"
#include "Net/UnrealNetwork.h"
#include "Kismet/GameplayStatics.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"

const FString UHMVRInteractableComponent::WorldStateApiUrl = TEXT(""); // set when world-state Lambda is deployed

UHMVRInteractableComponent::UHMVRInteractableComponent()
{
	SetIsReplicatedByDefault(true);
	PrimaryComponentTick.bCanEverTick = false;
}

void UHMVRInteractableComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(UHMVRInteractableComponent, State);
}

void UHMVRInteractableComponent::TransitionTo(EInteractableState NewState)
{
	AActor* Owner = GetOwner();
	if (!Owner || !Owner->HasAuthority()) return;
	if (NewState == State) return;

	State = NewState;
	TriggerAudio(NewState);
	OnStateChanged.Broadcast(NewState);

	if (bPersistent) PersistState();
}

void UHMVRInteractableComponent::OnRep_State()
{
	TriggerAudio(State);
	OnStateChanged.Broadcast(State);
}

void UHMVRInteractableComponent::TriggerAudio(EInteractableState ForState)
{
	if (USoundBase** Sound = SoundsByState.Find(ForState))
	{
		AActor* Owner = GetOwner();
		if (Owner && *Sound)
		{
			UGameplayStatics::SpawnSoundAtLocation(Owner, *Sound, Owner->GetActorLocation());
		}
	}
}

void UHMVRInteractableComponent::PersistState()
{
	if (WorldStateApiUrl.IsEmpty() || ObjectId.IsEmpty()) return;

	FString StateStr = UEnum::GetValueAsString(State);
	FString Body = FString::Printf(TEXT("{\"object_id\":\"%s\",\"state\":\"%s\"}"), *ObjectId, *StateStr);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(FString::Printf(TEXT("%s/world-state"), *WorldStateApiUrl));
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Req->SetContentAsString(Body);
	Req->OnProcessRequestComplete().BindUObject(this, &UHMVRInteractableComponent::OnPersistResponse);
	Req->ProcessRequest();
}

void UHMVRInteractableComponent::LoadState()
{
	if (WorldStateApiUrl.IsEmpty() || ObjectId.IsEmpty()) return;

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(FString::Printf(TEXT("%s/world-state/%s"), *WorldStateApiUrl, *ObjectId));
	Req->SetVerb(TEXT("GET"));
	Req->OnProcessRequestComplete().BindUObject(this, &UHMVRInteractableComponent::OnLoadResponse);
	Req->ProcessRequest();
}

void UHMVRInteractableComponent::OnPersistResponse(FHttpRequestPtr, FHttpResponsePtr Response, bool bConnected)
{
	if (!bConnected || !Response || Response->GetResponseCode() >= 500)
	{
		UE_LOG(LogTemp, Warning, TEXT("HMVRInteractable: failed to persist state for %s"), *ObjectId);
	}
}

void UHMVRInteractableComponent::OnLoadResponse(FHttpRequestPtr, FHttpResponsePtr Response, bool bConnected)
{
	if (!bConnected || !Response || Response->GetResponseCode() != 200) return;

	// Parse {"state":"Active"} and apply
	FString Body = Response->GetContentAsString();
	FString StateStr;
	if (FParse::Value(*Body, TEXT("state\":\""), StateStr))
	{
		StateStr = StateStr.Left(StateStr.Find(TEXT("\"")));
		const UEnum* Enum = StaticEnum<EInteractableState>();
		int64 Val = Enum ? Enum->GetValueByNameString(StateStr) : INDEX_NONE;
		if (Val != INDEX_NONE)
		{
			TransitionTo(static_cast<EInteractableState>(Val));
		}
	}
}
