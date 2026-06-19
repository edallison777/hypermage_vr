extends "res://scripts/interactable.gd"
const Diag = preload("res://scripts/debug_flags.gd")
# Proximity trigger (F2): an invisible Area3D that fires "interact:proximity"
# {id, entered} when the player (their CharacterBody) enters/leaves the region. A
# soft cue plays on transitions so it's observable on-device without diagnostics.

var _area: Area3D = null
var _count := 0

func _ready() -> void:
	super._ready()
	_area = get_node_or_null("Area")
	if _area:
		_area.body_entered.connect(_on_enter)
		_area.body_exited.connect(_on_exit)

func _on_enter(_b: Node) -> void:
	_count += 1
	if _count == 1:
		_fire(true)

func _on_exit(_b: Node) -> void:
	_count = maxi(0, _count - 1)
	if _count == 0:
		_fire(false)

func _fire(entered: bool) -> void:
	Audio.play_3d("ui_click", global_position, -6.0, 1.4 if entered else 0.9)
	fire_event("proximity", {"entered": entered})
	if Diag.ON:
		print("ProximityVolume: ", interactable_id, " entered=", entered)
