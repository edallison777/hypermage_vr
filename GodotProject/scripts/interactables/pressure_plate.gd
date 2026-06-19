extends "res://scripts/interactable.gd"
const Diag = preload("res://scripts/debug_flags.gd")
# Pressure plate (F2): an Area3D that presses when a physics body rests on it — the
# player's CharacterBody or a grabbed/thrown object (both on collision layer 1). The
# slab sinks; fires "interact:plate" {id, pressed} on the first body on / last body off.

var _area: Area3D = null
var _plate: Node3D = null
var _plate_rest: Vector3 = Vector3.ZERO
var _count := 0

func _ready() -> void:
	super._ready()
	_area = get_node_or_null("Area")
	_plate = get_node_or_null("Plate")
	if _plate:
		_plate_rest = _plate.position
	if _area:
		_area.body_entered.connect(_on_enter)
		_area.body_exited.connect(_on_exit)

func _on_enter(_b: Node) -> void:
	_count += 1
	if _count == 1:
		_set_pressed(true)

func _on_exit(_b: Node) -> void:
	_count = maxi(0, _count - 1)
	if _count == 0:
		_set_pressed(false)

# NB: not named _set() — that shadows Object._set(StringName, Variant) and fails to parse.
func _set_pressed(pressed: bool) -> void:
	if _plate:
		_plate.position = _plate_rest - Vector3(0.0, 0.03 if pressed else 0.0, 0.0)
	Audio.play_3d("ui_click", global_position, -2.0, 0.7 if pressed else 1.0)
	fire_event("plate", {"pressed": pressed})
	if Diag.ON:
		print("PressurePlate: ", interactable_id, " pressed=", pressed)
