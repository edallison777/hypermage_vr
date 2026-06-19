extends "res://test/test_base.gd"
# Unit tests for the F5 server-authoritative health model — the pure authority
# mutations (apply_damage / heal / revive) and the discrete bus events they broadcast.
# Run headless (no peer) so HealthManager acts as its own authority and the bus emits
# locally, exactly like offline play.

const HealthManager = preload("res://scripts/health_manager.gd")

var _events: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _cap(n: String, p: Dictionary) -> void:
	_events.append([n, p])

func _make(peer: int = 7) -> Node:
	var m = HealthManager.new()
	m.local_mode = true
	add_child(m)                 # _ready joins "health" + finds the autoload bus
	m.register(peer)
	return m

func _count(name: String) -> int:
	var c := 0
	for e in _events:
		if e[0] == name:
			c += 1
	return c

func test_register_full_hp() -> void:
	var m = _make()
	check_eq(m.get_hp(7), m.MAX_HP, "registered at full HP")
	check(not m.is_dead(7), "not dead on register")
	m.free()

func test_damage_reduces_hp() -> void:
	var m = _make()
	m.apply_damage(7, 30, "lava")
	check_eq(m.get_hp(7), m.MAX_HP - 30, "hp reduced by the damage amount")
	m.free()

func test_damage_clamps_and_dies_once() -> void:
	var m = _make()
	_events.clear()
	_bus().event.connect(_cap)
	m.apply_damage(7, 40, "lava")           # 60
	m.apply_damage(7, 40, "lava")           # 20
	check(not m.is_dead(7), "alive at 20")
	m.apply_damage(7, 40, "lava")           # -> clamps to 0, dies
	check_eq(m.get_hp(7), 0, "hp clamps at 0")
	check(m.is_dead(7), "dead at 0 HP")
	m.apply_damage(7, 40, "lava")           # ignored while dead
	check_eq(_count("health:died"), 1, "died fires exactly once across the 0-crossing")
	_bus().event.disconnect(_cap)
	m.free()

func test_dead_ignores_further_damage() -> void:
	var m = _make()
	m.apply_damage(7, 999, "lava")
	check(m.is_dead(7), "dead after lethal hit")
	m.apply_damage(7, 10, "lava")
	check_eq(m.get_hp(7), 0, "no further damage applied while dead")
	m.free()

func test_revive_restores_and_emits() -> void:
	var m = _make()
	m.apply_damage(7, 999, "lava")
	_events.clear()
	_bus().event.connect(_cap)
	m.revive(7)
	check_eq(m.get_hp(7), m.MAX_HP, "revive restores full HP")
	check(not m.is_dead(7), "alive again after revive")
	check_eq(_count("health:respawned"), 1, "respawned emitted once")
	_bus().event.disconnect(_cap)
	m.free()

func test_heal_clamps_and_ignored_when_dead() -> void:
	var m = _make()
	m.apply_damage(7, 50, "lava")           # 50
	m.heal(7, 80)                           # clamp at MAX
	check_eq(m.get_hp(7), m.MAX_HP, "heal clamps at max HP")
	m.apply_damage(7, 999, "lava")          # dead
	m.heal(7, 50)
	check_eq(m.get_hp(7), 0, "heal ignored while dead")
	m.free()

func test_changed_event_payload() -> void:
	var m = _make()
	_events.clear()
	_bus().event.connect(_cap)
	m.apply_damage(7, 25, "lava")
	var found := false
	for e in _events:
		if e[0] == "health:changed" and int(e[1].get("peer", -1)) == 7:
			found = true
			check_eq(int(e[1].get("hp")), m.MAX_HP - 25, "changed payload carries hp")
			check_eq(int(e[1].get("max")), m.MAX_HP, "changed payload carries max")
	check(found, "health:changed emitted for the damaged peer")
	_bus().event.disconnect(_cap)
	m.free()
