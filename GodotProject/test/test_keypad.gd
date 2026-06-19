extends "res://test/test_base.gd"
# Unit tests for the keypad accumulation logic (keypad.gd) — the pure text/caps/decimal
# rules + the Enter event. Keys are driven via _apply_key directly (the hand-touch poke
# + bus relay are exercised in the flat harness / on device).

const Keypad = preload("res://scripts/keypad.gd")

var _entered: Array = []

func _bus() -> Node:
	return get_tree().get_first_node_in_group("game_events")

func _cap(n: String, p: Dictionary) -> void:
	if n == "keypad:entered":
		_entered.append(p)

func _make(mode := "numeric") -> Node:
	var k = Keypad.new()
	k.keypad_id = "k"
	k.mode = mode
	add_child(k)            # _ready builds keys + display, connects the bus
	return k

func _type(k: Node, keys: Array) -> void:
	for key in keys:
		k._apply_key(str(key))

func test_numeric_entry() -> void:
	var k = _make("numeric")
	_type(k, ["4", "2", ".", "5"])
	check_eq(k.value(), "42.5", "digits + decimal accumulate")
	k.free()

func test_decimal_only_once() -> void:
	var k = _make("numeric")
	_type(k, ["4", ".", ".", "5"])
	check_eq(k.value(), "4.5", "second decimal point is ignored")
	k.free()

func test_delete_and_clear() -> void:
	var k = _make("numeric")
	_type(k, ["1", "2", "3"])
	k._apply_key("back")
	check_eq(k.value(), "12", "delete removes the last char")
	k._apply_key("clear")
	check_eq(k.value(), "", "clear empties the entry")
	k.free()

func test_letter_caps_toggle() -> void:
	var k = _make("letter")
	k._apply_key("A")                 # caps off -> lowercase
	k._apply_key("shift")             # caps on
	k._apply_key("B")
	k._apply_key(" ")
	check_eq(k.value(), "aB ", "shift toggles capitals for following letters")
	check(k.caps(), "caps flag is on after shift")
	k.free()

func test_enter_fires_value() -> void:
	var k = _make("numeric")
	_entered.clear()
	_bus().event.connect(_cap)
	_type(k, ["4", "2"])
	k._apply_key("enter")
	check_eq(_entered.size(), 1, "enter fires keypad:entered once")
	if _entered.size() == 1:
		check_eq(str(_entered[0].get("value")), "42", "entered payload carries the value")
		check_eq(str(_entered[0].get("id")), "k", "entered payload carries the keypad id")
	_bus().event.disconnect(_cap)
	k.free()
