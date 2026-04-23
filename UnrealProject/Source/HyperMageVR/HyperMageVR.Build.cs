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
			"HTTP",
			"UMG"
		});

		if (Target.Type == TargetType.Server)
		{
			PublicDependencyModuleNames.Add("GameLiftServerSDK");
		}

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			"Json",
			"JsonUtilities"
		});

		// VR-specific modules + Android manifest patch
		if (Target.Platform == UnrealTargetPlatform.Android)
		{
			PrivateDependencyModuleNames.AddRange(new string[]
			{
				"OpenXR",
				"OpenXRHMD",
				"OpenXRInput"
			});

			// Register the APL that forces bHasOBBFiles=false.
			// RunUAT always sets uebp_LOCAL_ROOT, making RequiresOBB() return true
			// unconditionally; the APL patches it back after manifest generation.
			AdditionalPropertiesForReceipt.Add("AndroidPlugin",
				System.IO.Path.Combine(ModuleDirectory, "HyperMageVR_APL.xml"));
		}
	}
}
