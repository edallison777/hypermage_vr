extends "res://test/test_base.gd"
# Unit tests for the F0 interaction framework: the GameEvents bus, the Reactor base,
# and Interactable.fire_event(). These exercise the LOCAL emit path (no multiplayer
# peer present, so fire() emits immediately); the networked server-relay path is
# validated by the 2-client integration test on device, since it needs real peers.
#
# All tests use the single autoload bus (the production source of truth, found via
# the "game_events" group) so that interactables/reactors — which also look it up by
# group — share the exact bus the test observes. Each test cleans up its own
# connections/nodes so suites don't leak into one another.

const Reactor = preload("res://scripts/reactor.gd")
const Interactable = preload("res://scripts/interactable.gd")

var _rec: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _capture(n: String, p: Dictionary) -> void:
	_rec.append([n, p])

func test_offline_fire_emits_locally() -> void:
	var bus := _bus()
	check(bus != null, "autoload GameEvents bus present in group")
	if bus == null:
		return
	_rec.clear()
	bus.event.connect(_capture)
	bus.fire("test:hello", {"x": 1})
	check_eq(_rec.size(), 1, "exactly one event emitted offline")
	if _rec.size() == 1:
		check_eq(_rec[0][0], "test:hello", "event name passthrough")
		check_eq(_rec[0][1].get("x"), 1, "payload passthrough")
	bus.event.disconnect(_capture)

func test_on_filters_by_name() -> void:
	var bus := _bus()
	if bus == null:
		check(false, "no bus")
		return
	var hits := [0]
	var cb := func(_p: Dictionary) -> void: hits[0] += 1
	bus.on("wanted", cb)
	bus.fire("unwanted", {})
	bus.fire("wanted", {})
	bus.fire("wanted", {})
	check_eq(hits[0], 2, "on() fires only for the matching name")
	# Tidy up the lambda connection we added (find it via the bus 'event' signal).
	for c in bus.event.get_connections():
		if c["callable"].get_method() == "":   # anonymous lambda wrapper
			bus.event.disconnect(c["callable"])

func test_reactor_reacts_to_its_trigger_only() -> void:
	var bus := _bus()
	if bus == null:
		check(false, "no bus")
		return
	var r = Reactor.new()
	r.trigger_event = "boom"
	var hits := [0]
	add_child(r)          # _ready connects to the autoload bus via group
	r.triggered.connect(func(_p: Dictionary) -> void: hits[0] += 1)
	bus.fire("nope", {})
	bus.fire("boom", {})
	check_eq(hits[0], 1, "reactor fires once, only on its trigger event")
	r.free()              # auto-disconnects its bus connection

func test_interactable_fires_scoped_event() -> void:
	var bus := _bus()
	if bus == null:
		check(false, "no bus")
		return
	_rec.clear()
	bus.event.connect(_capture)
	var it = Interactable.new()
	it.interactable_id = "lever_a"
	add_child(it)
	it.fire_event("activate", {"foo": 7})
	check_eq(_rec.size(), 1, "interactable fires one event")
	if _rec.size() == 1:
		check_eq(_rec[0][0], "interact:activate", "scoped event name")
		check_eq(_rec[0][1].get("id"), "lever_a", "interactable id folded into payload")
		check_eq(_rec[0][1].get("foo"), 7, "extra payload preserved")
	bus.event.disconnect(_capture)
	it.free()

func test_interactive_scripts_compile() -> void:
	# flat_harness.gd loops forever and vr_main.gd needs a scene, so they can't run
	# under the headless runner — but load() still compiles them, surfacing parse
	# errors as a null return. Guards the F0 edits to those files.
	# Includes the scripts that reference the Audio/Haptics autoload globals — a null
	# return would mean those globals don't resolve under the headless runner.
	for p in ["res://scripts/flat_harness.gd", "res://scripts/vr_main.gd",
			"res://scripts/reactors/light_reactor.gd",
			"res://scripts/audio_manager.gd", "res://scripts/haptics.gd",
			"res://scripts/grab_manager.gd", "res://scripts/mechanism_manager.gd",
			"res://scripts/secret_door.gd", "res://scripts/interactable_manager.gd",
			"res://scripts/interactables/push_button.gd",
			"res://scripts/interactables/toggle_switch.gd",
			"res://scripts/interactables/pressure_plate.gd",
			"res://scripts/interactables/proximity_volume.gd",
			"res://scripts/reactors/indicator_lamp.gd",
			"res://scripts/moving_platform.gd",
			"res://scripts/sequence_puzzle.gd",
			"res://scripts/health_manager.gd",
			"res://scripts/health_hud.gd",
			"res://scripts/interactables/hazard_volume.gd",
			"res://scripts/game_state.gd",
			"res://scripts/objective.gd",
			"res://scripts/game_rules.gd",
			"res://scripts/scoreboard.gd",
			"res://scripts/leaderboard_client.gd",
			"res://scripts/weapon.gd",
			"res://scripts/weapon_manager.gd",
			"res://scripts/combat_manager.gd",
			"res://scripts/target.gd",
			"res://scripts/ammo_pickup.gd"]:
		# load() returns the resource even on a parse error; can_instantiate() is false
		# unless the script actually compiled — so this catches parse failures.
		var s = load(p)
		check(s != null and s.can_instantiate(), "compiles: " + p)
