extends "res://test/test_base.gd"
# Unit tests for the F7 server-authoritative target health (combat_manager.gd) — the
# pure damage/destroy mutation + its bus events. The fire raycast is integration
# (flat harness / device); here we drive damage_target directly.

const CombatManager = preload("res://scripts/combat_manager.gd")

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
	var cm = CombatManager.new()
	cm.local_mode = true
	add_child(cm)
	return cm

func test_damage_reduces_target_hp() -> void:
	var cm = _make()
	cm.register_target("t1", 50)
	cm.damage_target("t1", 25)
	check_eq(cm.target_hp("t1"), 25, "hp reduced by damage")
	cm.free()

func test_destroy_fires_once_and_then_inert() -> void:
	var cm = _make()
	cm.register_target("t1", 50)
	_events.clear()
	_bus().event.connect(_cap)
	cm.damage_target("t1", 25)
	check(cm.target_hp("t1") == 25 and _count("target:destroyed") == 0, "not destroyed yet")
	cm.damage_target("t1", 25)               # -> 0
	check_eq(cm.target_hp("t1"), 0, "hp clamps at 0")
	check_eq(_count("target:destroyed"), 1, "destroyed fires exactly once")
	cm.damage_target("t1", 25)               # already dead -> ignored
	check_eq(_count("target:destroyed"), 1, "no second destroy")
	_bus().event.disconnect(_cap)
	cm.free()

func test_unregistered_target_ignored() -> void:
	var cm = _make()
	_events.clear()
	_bus().event.connect(_cap)
	cm.damage_target("ghost", 10)            # never registered
	check_eq(_count("target:hit"), 0, "unknown target produces no events")
	_bus().event.disconnect(_cap)
	cm.free()

func test_hit_event_payload() -> void:
	var cm = _make()
	cm.register_target("t1", 50)
	_events.clear()
	_bus().event.connect(_cap)
	cm.damage_target("t1", 10)
	var found := false
	for e in _events:
		if e[0] == "target:hit" and str(e[1].get("id")) == "t1":
			found = true
			check_eq(int(e[1].get("hp")), 40, "hit payload carries remaining hp")
			check_eq(int(e[1].get("max")), 50, "hit payload carries max hp")
	check(found, "target:hit emitted")
	_bus().event.disconnect(_cap)
	cm.free()
