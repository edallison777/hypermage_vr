// Copyright 2026 HyperMage. All Rights Reserved.

#include "HyperMageVR.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FHyperMageVRModule, HyperMageVR, "HyperMageVR");

void FHyperMageVRModule::StartupModule()
{
	// This code will execute after your module is loaded into memory
	UE_LOG(LogTemp, Log, TEXT("HyperMageVR module started"));
}

void FHyperMageVRModule::ShutdownModule()
{
	// This function may be called during shutdown to clean up your module
	UE_LOG(LogTemp, Log, TEXT("HyperMageVR module shutdown"));
}
