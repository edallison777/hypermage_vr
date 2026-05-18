// Copyright 2026 HyperMage. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class HyperMageVREditorTarget : TargetRules
{
	public HyperMageVREditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V6;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("HyperMageVR");
	}
}
