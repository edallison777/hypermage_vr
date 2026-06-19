extends "res://test/test_base.gd"
# Unit tests for the F3 moving platform: toggle (bus event flips endpoint) and auto
# (oscillates). The mechanism-link mode reuses the secret_door pattern (covered there).

const MovingPlatform = preload("res://scripts/moving_platform.gd")

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func test_toggle_flips_target_on_event() -> void:
	var bus := _bus()
	var p = MovingPlatform.new()
	p.mode = "toggle"
	p.source_id = "btn_lift"
	p.trigger_event = "interact:button"
	add_child(p)                              # _ready connects to the bus
	check_eq(p._target, 0.0, "starts at endpoint 0")
	bus.fire("interact:button", {"id": "btn_lift"})
	check_eq(p._target, 1.0, "matching event flips target to 1")
	bus.fire("interact:button", {"id": "btn_lift"})
	check_eq(p._target, 0.0, "second press flips back to 0")
	p.free()

func test_toggle_ignores_other_ids() -> void:
	var bus := _bus()
	var p = MovingPlatform.new()
	p.mode = "toggle"
	p.source_id = "btn_lift"
	add_child(p)
	bus.fire("interact:button", {"id": "other"})
	check_eq(p._target, 0.0, "event for a different id is ignored")
	p.free()

func test_auto_oscillates() -> void:
	var p = MovingPlatform.new()
	p.mode = "auto"
	p.auto_period = 4.0
	p.travel = Vector3(0, 2.0, 0)
	add_child(p)
	p._physics_process(1.0)                   # quarter period -> ~halfway up
	check(p._cur > 0.1, "auto value advances above 0")
	check(p._cur <= 1.0, "auto value stays within range")
	p.free()
