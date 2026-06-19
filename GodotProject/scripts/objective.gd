extends Node3D
# Objective marker (F6 — see GodotProject/FEATURE_PLAN.md). An invisible, converter-
# generated data node (like sequence_puzzle) that GameState.begin() scans from the
# "objective" group. It carries no logic itself: GameState watches the bus for
# `trigger_event` (with payload.id == match_id, if set) and credits this objective.
#
# Example: {objective_id:"reach_altar", trigger_event:"interact:plate", match_id:"altar",
#           points:150, optional:false}. Sequence/secret-door/proximity events work too.

@export var objective_id: String = ""
@export var trigger_event: String = "interact:button"
@export var match_id: String = ""        # if set, payload.id must equal this
@export var points: int = 100
@export var optional: bool = false

func _ready() -> void:
	add_to_group("objective")
