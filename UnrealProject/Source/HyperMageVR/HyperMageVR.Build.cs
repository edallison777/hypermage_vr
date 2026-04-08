// Copyright 2026 HyperMage. All Rights Reserved.

using UnrealBuildTool;

public class HyperMageVR : ModuleRules
{
	public HyperMageVR(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"HeadMountedDisplay",
			"OnlineSubsystem",
			"OnlineSubsystemUtils",
			"GameLiftServerSDK",
			"HTTP"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			"Json",
			"JsonUtilities"
		});

		// OpenSSL — required by AwsSigV4 for HMAC-SHA256 signing of session-summary requests
		AddEngineThirdPartyPrivateStaticDependencies(Target, "OpenSSL");

		// VR-specific modules
		if (Target.Platform == UnrealTargetPlatform.Android)
		{
			PrivateDependencyModuleNames.AddRange(new string[]
			{
				"OpenXR",
				"OpenXRHMD",
				"OpenXRInput"
			});
		}
	}
}
