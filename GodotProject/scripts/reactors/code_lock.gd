extends Node3D
const Diag = preload("res://scripts/debug_flags.gd")
# Code lock (input-devices feature). Listens for a keypad's "keypad:entered" {id, value}
# and, if the value matches `code`, fires `opened_event` {id} so a lamp / door reactor
# can respond. Demonstrates the keypad's output driving a puzzle. One-shot.
#
# Derived deterministically from the (server-sequenced) keypad:entered on every peer,
# so it emits the open event LOCALLY (like the F4 sequence solve) — no re-broadcast.

@export var lock_id: String = ""
@export var keypad_id: String = ""
@export var code: String = ""
@export var opened_event: String = "lock:opened"

var _opened := false
var _bus: Node = null

func _ready() -> void:
	add_to_group("code_lock")
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)

func is_open() -> bool:
	return _opened

func _on_event(name: String, payload: Dictionary) -> void:
	if _opened or name != "keypad:entered":
		return
	if str(payload.get("id", "")) != keypad_id:
		return
	if str(payload.get("value", "")) == code:
		_opened = true
		Audio.play_3d("success", global_position, 0.0, 1.0)
		if _bus:
			_bus.fire_local(opened_event, {"id": lock_id})
		if Diag.ON:
			print("CodeLock: ", lock_id, " OPENED")
