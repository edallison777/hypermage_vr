extends "res://scripts/interactable.gd"
const Diag = preload("res://scripts/debug_flags.gd")
# Latching on/off switch (F2). Hand-touch flips it; fires "interact:switch" {id, on}.
# The lever tilts to show state; pitch of the click rises for on, falls for off.

const PRESS_RADIUS := 0.12

var _on := false
var _lever: Node3D = null

func _ready() -> void:
	super._ready()
	add_to_group("hand_touch")
	_lever = get_node_or_null("Lever")
	_apply()

func press_radius() -> float:
	return PRESS_RADIUS

func handle_global_position() -> Vector3:
	return _lever.global_position if _lever else global_position

func activate(side: String) -> void:
	_on = not _on
	_apply()
	Audio.play_3d("ui_click", handle_global_position(), -1.0, 1.2 if _on else 0.85)
	Haptics.pulse(side, 0.5, 0.04)
	fire_event("switch", {"on": _on})
	if Diag.ON:
		print("ToggleSwitch: ", interactable_id, " -> ", _on)

func is_on() -> bool:
	return _on

func _apply() -> void:
	if _lever:
		_lever.rotation_degrees.x = -35.0 if _on else 35.0
