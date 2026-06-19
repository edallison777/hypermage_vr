extends "res://test/test_base.gd"
# Unit tests for the F2 simple interactables. Each instantiates the script (its
# visual child nodes are absent here, which the scripts guard for), drives the
# activation path, and asserts the correct discrete event reaches the autoload bus.

const PushButton = preload("res://scripts/interactables/push_button.gd")
const ToggleSwitch = preload("res://scripts/interactables/toggle_switch.gd")
const PressurePlate = preload("res://scripts/interactables/pressure_plate.gd")
const ProximityVolume = preload("res://scripts/interactables/proximity_volume.gd")

var _rec: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _cap(n: String, p: Dictionary) -> void:
	_rec.append([n, p])

func test_button_fires_interact_button() -> void:
	var bus := _bus()
	_rec.clear()
	bus.event.connect(_cap)
	var btn = PushButton.new()
	btn.interactable_id = "btn_a"
	add_child(btn)
	btn.activate("left")
	bus.event.disconnect(_cap)
	btn.free()
	check_eq(_rec.size(), 1, "button fires one event")
	if _rec.size() == 1:
		check_eq(_rec[0][0], "interact:button", "button event name")
		check_eq(_rec[0][1].get("id"), "btn_a", "button id in payload")

func test_button_debounces_while_down() -> void:
	var bus := _bus()
	_rec.clear()
	bus.event.connect(_cap)
	var btn = PushButton.new()
	btn.interactable_id = "btn_a"
	add_child(btn)
	btn.activate("left")
	btn.activate("left")        # still down -> ignored
	bus.event.disconnect(_cap)
	btn.free()
	check_eq(_rec.size(), 1, "second activate while down is ignored")

func test_switch_toggles_state() -> void:
	var bus := _bus()
	_rec.clear()
	bus.event.connect(_cap)
	var sw = ToggleSwitch.new()
	sw.interactable_id = "sw_a"
	add_child(sw)
	sw.activate("left")         # -> on
	sw.activate("left")         # -> off
	bus.event.disconnect(_cap)
	sw.free()
	check_eq(_rec.size(), 2, "switch fires per toggle")
	if _rec.size() == 2:
		check_eq(_rec[0][0], "interact:switch", "switch event name")
		check_eq(_rec[0][1].get("on"), true, "first toggle on=true")
		check_eq(_rec[1][1].get("on"), false, "second toggle on=false")

func test_plate_fires_first_on_last_off() -> void:
	var bus := _bus()
	_rec.clear()
	bus.event.connect(_cap)
	var p = PressurePlate.new()
	p.interactable_id = "plate_a"
	add_child(p)
	p._on_enter(null)           # first body -> pressed
	p._on_enter(null)           # second body -> no new event
	p._on_exit(null)
	p._on_exit(null)            # last body off -> released
	bus.event.disconnect(_cap)
	p.free()
	check_eq(_rec.size(), 2, "plate fires on first-on and last-off only")
	if _rec.size() == 2:
		check_eq(_rec[0][1].get("pressed"), true, "pressed=true first")
		check_eq(_rec[1][1].get("pressed"), false, "pressed=false last")

func test_proximity_fires_enter_exit() -> void:
	var bus := _bus()
	_rec.clear()
	bus.event.connect(_cap)
	var pv = ProximityVolume.new()
	pv.interactable_id = "prox_a"
	add_child(pv)
	pv._on_enter(null)
	pv._on_exit(null)
	bus.event.disconnect(_cap)
	pv.free()
	check_eq(_rec.size(), 2, "proximity fires enter + exit")
	if _rec.size() == 2:
		check_eq(_rec[0][1].get("entered"), true, "entered=true")
		check_eq(_rec[1][1].get("entered"), false, "entered=false")
