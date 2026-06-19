extends "res://scripts/interactable.gd"
const Diag = preload("res://scripts/debug_flags.gd")
# Momentary push button (F2). InteractableManager calls activate(side) when a hand
# enters the press zone. Blips the cap down, clicks + buzzes, and fires
# "interact:button" {id} on the bus for reactors / the F4 sequence. Auto-pops back up.

const PRESS_RADIUS := 0.10
const POP_TIME := 0.15
const DEPRESS := 0.025

var _cap: Node3D = null
var _cap_rest: Vector3 = Vector3.ZERO
var _down := false
var _pop_t := 0.0

func _ready() -> void:
	super._ready()                       # interactable.gd: group "interactable" + bus ref
	add_to_group("hand_touch")
	_cap = get_node_or_null("Cap")
	if _cap:
		_cap_rest = _cap.position

func press_radius() -> float:
	return PRESS_RADIUS

func handle_global_position() -> Vector3:
	return _cap.global_position if _cap else global_position

func activate(side: String) -> void:
	if _down:
		return
	_down = true
	_pop_t = POP_TIME
	if _cap:
		_cap.position = _cap_rest - Vector3(0.0, DEPRESS, 0.0)
	Audio.play_3d("ui_click", handle_global_position())
	Haptics.pulse(side, 0.4, 0.03)
	fire_event("button")
	if Diag.ON:
		print("PushButton: ", interactable_id, " pressed")

func _process(dt: float) -> void:
	if not _down:
		return
	_pop_t -= dt
	if _pop_t <= 0.0:
		_down = false
		if _cap:
			_cap.position = _cap_rest
