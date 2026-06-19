extends Node3D
const Diag = preload("res://scripts/debug_flags.gd")
# A single key of a keypad (input-devices feature). Built procedurally by keypad.gd,
# joins the "hand_touch" group so the existing InteractableManager pokes it with the
# fingertip (rising-edge). On press it fires a network-consistent "keypad:key"
# {id, key} on the F0 bus; the owning keypad listens and accumulates, so every peer's
# display derives the same text from the server-sequenced key stream.
#
# Keys sit close together, so the press radius is much tighter than a standalone
# button's (0.10) — otherwise one poke would trigger several neighbours at once.

const PRESS_RADIUS := 0.028

@export var keypad_id: String = ""
@export var key_value: String = ""

var _cap: Node3D = null
var _cap_rest := Vector3.ZERO
var _down := false
var _pop_t := 0.0
var _bus: Node = null

func _ready() -> void:
	add_to_group("hand_touch")
	_cap = get_node_or_null("Cap")
	if _cap:
		_cap_rest = _cap.position
	_bus = get_tree().get_first_node_in_group("game_events")

func press_radius() -> float:
	return PRESS_RADIUS

func handle_global_position() -> Vector3:
	return _cap.global_position if _cap else global_position

func activate(side: String) -> void:
	if _down:
		return
	_down = true
	_pop_t = 0.12
	if _cap:
		_cap.position = _cap_rest - Vector3(0, 0.012, 0)
	Audio.play_3d("ui_click", handle_global_position(), -3.0, 1.3)
	Haptics.pulse(side, 0.35, 0.02)
	if _bus == null:
		_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.fire("keypad:key", {"id": keypad_id, "key": key_value})
	if Diag.ON:
		print("KeypadKey: ", keypad_id, " <- ", key_value)

func _process(dt: float) -> void:
	if not _down:
		return
	_pop_t -= dt
	if _pop_t <= 0.0:
		_down = false
		if _cap:
			_cap.position = _cap_rest
