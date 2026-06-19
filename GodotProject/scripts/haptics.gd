extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Haptics primitive (F1 — see GodotProject/FEATURE_PLAN.md). Autoload "Haptics".
#
# Fires controller rumble via the OpenXR "haptic" output action (already bound to
# both hands in openxr_action_map.tres). Two entry points:
#  - pulse_controller(ctrl, ...): callers that already hold an XRController3D ref
#    (grab_manager, mechanism_manager) — the direct, cheap path.
#  - pulse(side, ...): "left"/"right"/"both", resolving controllers lazily by
#    scanning for XRController3D nodes (for event-driven haptics that lack a ref).
#
# Safe everywhere: with no controllers present (flat mode / headless / server) it
# simply no-ops.

const ACTION := "haptic"

var _left: XRController3D = null
var _right: XRController3D = null

# Direct: pulse a specific controller. amplitude 0..1, duration seconds.
func pulse_controller(ctrl, amplitude := 0.5, duration := 0.08, frequency := 0.0) -> void:
	if ctrl is XRController3D:
		ctrl.trigger_haptic_pulse(ACTION, frequency, clampf(amplitude, 0.0, 1.0), duration, 0.0)

# By side: "left" / "right" / "both".
func pulse(side := "both", amplitude := 0.5, duration := 0.08) -> void:
	_resolve()
	if side == "left" or side == "both":
		pulse_controller(_left, amplitude, duration)
	if side == "right" or side == "both":
		pulse_controller(_right, amplitude, duration)

func _resolve() -> void:
	if is_instance_valid(_left) and is_instance_valid(_right):
		return
	for c in _find_controllers(get_tree().root, []):
		if c.tracker == "left_hand":
			_left = c
		elif c.tracker == "right_hand":
			_right = c

func _find_controllers(n: Node, acc: Array) -> Array:
	if n is XRController3D:
		acc.append(n)
	for c in n.get_children():
		_find_controllers(c, acc)
	return acc
