extends "res://test/test_base.gd"
# Unit tests for the F4 sequence puzzle — pure state-machine logic driven through the
# bus (no peer -> events emit locally). Covers advance, wrong-resets, the forgiving
# restart-at-1, unrelated-id-ignored, single solve, and post-solve inertness.

const SequencePuzzle = preload("res://scripts/sequence_puzzle.gd")

var _solved_rec: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _cap(n: String, p: Dictionary) -> void:
	if n == "sequence:solved":
		_solved_rec.append(p)

func _make(order: Array) -> Node:
	var s = SequencePuzzle.new()
	s.puzzle_id = "seq1"
	s.order = order
	add_child(s)                 # _ready connects to the autoload bus
	return s

func _press(bus: Node, id: String) -> void:
	bus.fire("interact:button", {"id": id})

func test_correct_order_solves_once() -> void:
	var bus := _bus()
	_solved_rec.clear()
	bus.event.connect(_cap)
	var s = _make(["b3", "b1", "b4", "b2"])
	_press(bus, "b3"); _press(bus, "b1"); _press(bus, "b4")
	check(not s.is_solved(), "not solved before the last step")
	_press(bus, "b2")
	check(s.is_solved(), "solved after the full order")
	check_eq(_solved_rec.size(), 1, "sequence:solved emitted exactly once")
	if _solved_rec.size() == 1:
		check_eq(_solved_rec[0].get("id"), "seq1", "solved payload carries puzzle id")
	bus.event.disconnect(_cap)
	s.free()

func test_wrong_step_resets() -> void:
	var bus := _bus()
	var s = _make(["b3", "b1", "b4", "b2"])
	_press(bus, "b3")
	check_eq(s.progress(), 1, "advanced to 1")
	_press(bus, "b4")            # expected b1; b4 != order[0] -> full reset
	check_eq(s.progress(), 0, "wrong step resets to 0")
	s.free()

func test_wrong_but_first_step_restarts_at_one() -> void:
	var bus := _bus()
	var s = _make(["b3", "b1", "b4", "b2"])
	_press(bus, "b3"); _press(bus, "b1")
	check_eq(s.progress(), 2, "advanced to 2")
	_press(bus, "b3")            # expected b4; but b3 == order[0] -> restart at 1
	check_eq(s.progress(), 1, "pressing the start again restarts at 1")
	s.free()

func test_unrelated_id_ignored() -> void:
	var bus := _bus()
	var s = _make(["b3", "b1"])
	_press(bus, "b3")
	_press(bus, "zzz")           # not part of the puzzle -> ignored, no reset
	check_eq(s.progress(), 1, "unrelated id neither advances nor resets")
	s.free()

func test_post_solve_is_inert() -> void:
	var bus := _bus()
	_solved_rec.clear()
	bus.event.connect(_cap)
	var s = _make(["b3", "b1"])
	_press(bus, "b3"); _press(bus, "b1")
	check(s.is_solved(), "solved")
	_press(bus, "b3"); _press(bus, "b1")   # further presses ignored
	check_eq(_solved_rec.size(), 1, "no further solves after solved")
	bus.event.disconnect(_cap)
	s.free()
