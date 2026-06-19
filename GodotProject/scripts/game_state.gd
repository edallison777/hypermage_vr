extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Server-authoritative scoring + objectives + win/lose (F6 — see GodotProject/FEATURE_PLAN.md).
#
# Mirrors HealthManager's authority model: the SERVER (or, offline, this node as its own
# authority) is the only place score/objective/win-lose state is decided. It watches the
# F0 GameEvents bus for the discrete events that complete objectives (button presses,
# sequence solves, plate triggers, …) and for F5 deaths, evaluates the rules, and
# broadcasts the RESULTS back over the bus:
#   score:changed {score, delta, reason}     (team score — co-op PvE, shared)
#   objective:completed {id, points}
#   game:time {left}                          (countdown tick, ~1/s)
#   game:won {score, objectives}
#   game:lost {reason}
# Clients run this node too (path-matched in both scenes) but stay PASSIVE — only the
# authority evaluates; the scoreboard UI derives purely from the broadcast events.
#
# Lives at /root/HMVRGame/GameState. Objectives + rules are CONVERTER-GENERATED room
# data: invisible nodes in groups "objective" / "game_rules" that begin() scans.

const EV_SCORE     := "score:changed"
const EV_OBJECTIVE := "objective:completed"
const EV_TIME      := "game:time"
const EV_WON       := "game:won"
const EV_LOST      := "game:lost"

signal score_changed(score: int)
signal objective_completed(id: String)
signal game_ended(won: bool, reason: String)

var local_mode := false

var _score := 0
var _objectives := {}        # id -> {done, points, optional, event, match_id}
var _required_open := 0      # non-optional objectives not yet done
var _ended := false
var _started := false
var _time_left := -1.0       # <0 = no limit
var _deaths := 0
var _max_deaths := -1        # <0 = deaths never lose
var _tick_accum := 0.0
var _bus: Node = null

func _ready() -> void:
	add_to_group("game_state")
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)

# Server: called by server_main after the room (and its objective nodes) is loaded.
func setup() -> void:
	if multiplayer.is_server():
		begin()

# Offline (local room / flat harness): self-authoritative.
func setup_offline() -> void:
	local_mode = true
	begin()

func _authority() -> bool:
	return local_mode or not multiplayer.has_multiplayer_peer() or multiplayer.is_server()

# Scan converter-generated objective/rules nodes and (re)start the round. Idempotent.
func begin() -> void:
	_score = 0
	_objectives.clear()
	_required_open = 0
	_ended = false
	_deaths = 0
	_time_left = -1.0
	_max_deaths = -1
	_tick_accum = 0.0
	for r in get_tree().get_nodes_in_group("game_rules"):
		_time_left = float(r.time_limit) if float(r.time_limit) > 0.0 else -1.0
		_max_deaths = int(r.max_team_deaths)
	for o in get_tree().get_nodes_in_group("objective"):
		add_objective(str(o.objective_id), str(o.trigger_event), str(o.match_id),
				int(o.points), bool(o.optional))
	_started = true
	if Diag.ON:
		print("GameState: begin objectives=", _objectives.size(), " required_open=",
				_required_open, " time=", _time_left, " max_deaths=", _max_deaths)

# Register one objective. Primitive used by begin() and directly by unit tests.
func add_objective(id: String, event: String, match_id := "", points := 100,
		optional := false) -> void:
	if id == "" or _objectives.has(id):
		return
	_objectives[id] = {"done": false, "points": points, "optional": optional,
			"event": event, "match_id": match_id}
	if not optional:
		_required_open += 1

# ── Queries ────────────────────────────────────────────────────────────────────────

func score() -> int:
	return _score

func is_objective_done(id: String) -> bool:
	return _objectives.has(id) and _objectives[id]["done"]

func objectives_done() -> int:
	var n := 0
	for id in _objectives:
		if _objectives[id]["done"]:
			n += 1
	return n

func objectives_total() -> int:
	return _objectives.size()

func has_ended() -> bool:
	return _ended

func time_left() -> float:
	return _time_left

# ── Authoritative evaluation ─────────────────────────────────────────────────────────

func _on_event(name: String, payload: Dictionary) -> void:
	if _ended or not _started or not _authority():
		return
	if name == "health:died":
		_deaths += 1
		if _max_deaths >= 0 and _deaths > _max_deaths:
			_lose("team wiped")
		return
	# An objective completes on its trigger event (optionally matching a payload id).
	for id in _objectives:
		var o: Dictionary = _objectives[id]
		if o["done"] or name != o["event"]:
			continue
		if o["match_id"] != "" and str(payload.get("id", "")) != o["match_id"]:
			continue
		_complete_objective(id)
		break

func _complete_objective(id: String) -> void:
	var o: Dictionary = _objectives[id]
	o["done"] = true
	if not o["optional"]:
		_required_open -= 1
	add_score(int(o["points"]), "objective:" + id)
	_emit(EV_OBJECTIVE, {"id": id, "points": o["points"]})
	objective_completed.emit(id)
	if Diag.ON:
		print("GameState: objective ", id, " done (+", o["points"], ")")
	if _required_open <= 0:
		_win()

# Pure: adjust the shared team score and broadcast. Directly unit-tested.
func add_score(points: int, reason := "") -> void:
	_score = maxi(0, _score + points)
	_emit(EV_SCORE, {"score": _score, "delta": points, "reason": reason})
	score_changed.emit(_score)

func _win() -> void:
	if _ended:
		return
	_ended = true
	_emit(EV_WON, {"score": _score, "objectives": objectives_total()})
	game_ended.emit(true, "objectives complete")

func _lose(reason: String) -> void:
	if _ended:
		return
	_ended = true
	_emit(EV_LOST, {"reason": reason})
	game_ended.emit(false, reason)

# Countdown (authority only). Split out of _process so tests can drive it deterministically.
func tick(delta: float) -> void:
	if _ended or not _started or not _authority() or _time_left < 0.0:
		return
	_time_left = maxf(0.0, _time_left - delta)
	_tick_accum += delta
	if _tick_accum >= 1.0:
		_tick_accum -= 1.0
		_emit(EV_TIME, {"left": int(ceil(_time_left))})
	if _time_left <= 0.0 and _required_open > 0:
		_lose("time up")

func _process(delta: float) -> void:
	tick(delta)

func _emit(name: String, payload: Dictionary) -> void:
	if _bus == null:
		_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.fire(name, payload)
