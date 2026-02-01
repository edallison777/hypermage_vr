// Copyright 2026 HyperMage. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class HyperMageVRServerTarget : TargetRules
{
	public HyperMageVRServerTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Server;
		DefaultBuildSettings = BuildSettingsVersion.V4;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_3;
		ExtraModuleNames.Add("HyperMageVR");
		
		// Server-specific optimizations
		bUseLoggingInShipping = true;
		bCompileWithAccessibilitySupport = false;
		bCompileAgainstEngine = true;
		bCompileAgainstCoreUObject = true;
	}
}
