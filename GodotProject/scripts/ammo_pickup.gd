extends Node3D
# Ammo pickup (F7 — see GodotProject/FEATURE_PLAN.md). An Area3D that reloads the
# local player's equipped weapon(s) when they walk into it, then consumes itself.
# Client-side (ammo is local weapon state, like the F5 hazard's local detection).

@export var pickup_id: String = ""

var _area: Area3D = null
var _used := false

func _ready() -> void:
	add_to_group("ammo_pickup")
	_area = get_node_or_null("Area")
	if _area:
		_area.body_entered.connect(_on_enter)

func _on_enter(b: Node) -> void:
	if _used or not b.is_in_group("player"):
		return
	var reloaded := false
	for w in get_tree().get_nodes_in_group("weapon"):
		if str(w.equipped_by) != "":
			w.reload()
			reloaded = true
	if not reloaded:
		return                          # nothing equipped — leave the pickup for later
	_used = true
	Audio.play_3d("ui_click", global_position, 0.0, 1.5)
	visible = false
	if _area:
		_area.monitoring = false
