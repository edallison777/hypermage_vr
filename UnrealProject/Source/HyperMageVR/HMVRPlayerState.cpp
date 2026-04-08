// Copyright 2026 HyperMage. All Rights Reserved.

#include "HMVRPlayerState.h"
#include "Net/UnrealNetwork.h"

void AHMVRPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AHMVRPlayerState, CognitoPlayerId);
}
