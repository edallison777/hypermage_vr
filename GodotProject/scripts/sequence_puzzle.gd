extends Node3D
const Diag = preload("res://scripts/debug_flags.gd")
# Ordered-interaction puzzle (F4 — see GodotProject/FEATURE_PLAN.md).
#
# Watches a bus event (default "interact:button") for the interactable ids in `order`.
# They must fire in that exact order:
#   - correct next id  -> advance (rising click); completing the list -> SOLVE
#   - wrong id (but one that's part of this puzzle) -> reset to 0 (dull click); if the
#     wrong id is actually order[0], restart at 1 (pressing the start again is forgiving)
#   - an id not in `order` -> ignored (unrelated interactables don't break the puzzle)
#
# On solve it emits `solved_event` {id = puzzle_id} via the bus's fire_LOCAL: every peer
# runs this puzzle and consumes the same server-sequenced input events in the same order,
# so each peer solves at the same point and a local emit keeps reactions consistent
# without N-fold re-broadcast. One-shot: stays solved. (Late joiners won't have the prior
# input history — acceptable for a co-op puzzle; revisit if it matters.)

signal advanced(progress: int)
signal reset_to_zero()
signal solved()

@export var puzzle_id: String = ""
@export var watch_event: String = "interact:button"
@export var order: Array = []
@export var reset_on_wrong: bool = true
@export var solved_event: String = "sequence:solved"

var _progress := 0
var _solved := false
var _bus: Node = null

func _ready() -> void:
	add_to_group("sequence_puzzle")
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)

func progress() -> int:
	return _progress

func is_solved() -> bool:
	return _solved

func _on_event(event_name: String, payload: Dictionary) -> void:
	if _solved or event_name != watch_event:
		return
	var id := str(payload.get("id", ""))
	if not order.has(id):
		return                                  # not part of this puzzle
	if id == str(order[_progress]):
		_progress += 1
		_feedback("advance")
		advanced.emit(_progress)
		if _progress >= order.size():
			_solve()
	elif reset_on_wrong:
		_progress = 1 if id == str(order[0]) else 0   # forgiving restart on the first step
		_feedback("reset")
		reset_to_zero.emit()

func _solve() -> void:
	_solved = true
	_feedback("solved")
	solved.emit()
	if _bus:
		_bus.fire_local(solved_event, {"id": puzzle_id})
	if Diag.ON:
		print("SequencePuzzle: ", puzzle_id, " SOLVED")

func _feedback(kind: String) -> void:
	match kind:
		"advance":
			Audio.play_3d("ui_click", global_position, 0.0, 1.0 + 0.12 * _progress)
		"reset":
			Audio.play_3d("ui_click", global_position, -1.0, 0.5)
		"solved":
			Audio.play_3d("success", global_position, 0.0, 1.0)
