extends RefCounted
# Single switch for VR diagnostic logging/labels (XRDIAG, MECHDIAG, MechMgr,
# Mechanism:, SecretDoor:, GrabManager: prints + the in-world DebugLabel).
# Left in place deliberately so they can be re-enabled fast if VR input or
# mechanism/door behaviour regresses. Flip to true, rebuild, sideload.
const ON := false
