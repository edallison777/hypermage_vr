// Copyright 2026 HyperMage. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class HyperMageVRTarget : TargetRules
{
	public HyperMageVRTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V4;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_3;
		ExtraModuleNames.Add("HyperMageVR");
	}
}
