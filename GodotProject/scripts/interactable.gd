extends Node3D
# Base contract for hand-operable objects (F0 — see GodotProject/FEATURE_PLAN.md).
#
# A common spine for things the player operates by hand. The existing lever/wheel
# (mechanism.gd) are NOT reparented onto this in F0 (additive-only; they stay as
# device-verified); buttons / pressure plates / switches (F2) will extend this.
#
# Provides: a stable `interactable_id`, group membership for proximity scans, an
# overridable handle position, and fire_event() — a scoped, network-consistent
# discrete event routed through the GameEvents bus (found via group, like reactors).

@export var interactable_id: String = ""

var _bus: Node = null

func _ready() -> void:
	add_to_group("interactable")
	_bus = get_tree().get_first_node_in_group("game_events")

# World position the hand must reach to operate this. Override for moving handles
# (the lever/wheel track their pivot); default is the node origin.
func handle_global_position() -> Vector3:
	return global_position

# Emit a discrete event scoped to this interactable: name "interact:<verb>", with
# the interactable id folded into the payload. Network-consistent via the bus.
func fire_event(verb: String, extra: Dictionary = {}) -> void:
	if _bus == null:
		_bus = get_tree().get_first_node_in_group("game_events")
	if _bus == null:
		push_warning("Interactable '%s': no GameEvents bus" % name)
		return
	var p := extra.duplicate()
	p["id"] = interactable_id
	_bus.fire("interact:%s" % verb, p)
