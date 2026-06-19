extends "res://test/test_base.gd"
# Unit tests for the F6 scoring / objectives / win-lose authority (game_state.gd).
# Run headless (no peer) so GameState is its own authority and the bus emits locally.
# Tests register objectives directly (skipping begin()'s node scan) and drive the
# trigger events through the bus, exactly as the server would in play.

const GameState = preload("res://scripts/game_state.gd")

var _events: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _cap(n: String, p: Dictionary) -> void:
	_events.append([n, p])

func _count(name: String) -> int:
	var c := 0
	for e in _events:
		if e[0] == name:
			c += 1
	return c

func _make() -> Node:
	var g = GameState.new()
	g.local_mode = true
	add_child(g)            # _ready connects to the autoload bus
	return g

func _arm(g: Node) -> void:
	g._started = true       # objectives added manually; skip begin()'s group scan

func _fire(name: String, payload: Dictionary) -> void:
	_bus().fire(name, payload)

func test_objective_awards_and_completes_once() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	_arm(g)
	_events.clear()
	_bus().event.connect(_cap)
	_fire("interact:button", {"id": "b1"})
	check(g.is_objective_done("o1"), "objective marked done")
	check_eq(g.score(), 100, "points awarded")
	check_eq(_count("objective:completed"), 1, "objective:completed once")
	_fire("interact:button", {"id": "b1"})   # repeat press ignored
	check_eq(g.score(), 100, "no double award on repeat trigger")
	_bus().event.disconnect(_cap)
	g.free()

func test_match_id_filters() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	_arm(g)
	_fire("interact:button", {"id": "b2"})    # wrong id
	check(not g.is_objective_done("o1"), "non-matching id does not complete")
	_fire("interact:button", {"id": "b1"})
	check(g.is_objective_done("o1"), "matching id completes")
	g.free()

func test_all_required_win_optional_ignored() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	g.add_objective("o2", "interact:button", "b2", 100)
	g.add_objective("o3", "interact:button", "b3", 150, true)   # optional bonus
	_arm(g)
	_events.clear()
	_bus().event.connect(_cap)
	_fire("interact:button", {"id": "b1"})
	check(not g.has_ended(), "not won until all REQUIRED done")
	_fire("interact:button", {"id": "b2"})
	check(g.has_ended(), "won once both required objectives done")
	check_eq(_count("game:won"), 1, "game:won fired once (optional not required)")
	_bus().event.disconnect(_cap)
	g.free()

func test_post_win_is_inert() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	_arm(g)
	_events.clear()
	_bus().event.connect(_cap)
	_fire("interact:button", {"id": "b1"})    # only required -> win
	check(g.has_ended(), "won")
	var score_after_win: int = g.score()
	_fire("interact:button", {"id": "b1"})
	check_eq(g.score(), score_after_win, "no scoring after the game ends")
	check_eq(_count("game:won"), 1, "no second win")
	_bus().event.disconnect(_cap)
	g.free()

func test_time_up_loses() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	_arm(g)
	g._time_left = 1.0
	_events.clear()
	_bus().event.connect(_cap)
	g.tick(2.0)              # runs the clock past zero with a required objective open
	check(g.has_ended(), "game ended on timeout")
	check_eq(_count("game:lost"), 1, "game:lost fired once")
	_bus().event.disconnect(_cap)
	g.free()

func test_deaths_lose() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 100)
	_arm(g)
	g._max_deaths = 2
	_events.clear()
	_bus().event.connect(_cap)
	_fire("health:died", {"peer": 1})
	_fire("health:died", {"peer": 1})
	check(not g.has_ended(), "alive within the death cap")
	_fire("health:died", {"peer": 1})        # exceeds max_team_deaths
	check(g.has_ended(), "lost once deaths exceed the cap")
	check_eq(_count("game:lost"), 1, "game:lost fired once")
	_bus().event.disconnect(_cap)
	g.free()

func test_score_changed_payload() -> void:
	var g = _make()
	g.add_objective("o1", "interact:button", "b1", 75)
	_arm(g)
	_events.clear()
	_bus().event.connect(_cap)
	_fire("interact:button", {"id": "b1"})
	var found := false
	for e in _events:
		if e[0] == "score:changed":
			found = true
			check_eq(int(e[1].get("score")), 75, "score:changed carries running total")
			check_eq(int(e[1].get("delta")), 75, "score:changed carries the delta")
	check(found, "score:changed emitted")
	_bus().event.disconnect(_cap)
	g.free()
