extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Hand-touch input for buttons/switches (F2 — see GodotProject/FEATURE_PLAN.md).
# Lives at /root/HMVRGame/InteractableManager in both scenes (client + server).
#
# Polls the two controllers each frame against every node in the "hand_touch" group
# and calls activate(side) on the RISING EDGE of a controller entering a node's press
# zone (so holding your hand there fires once, not every frame). This is local input
# only — the interactable fires its own network-consistent bus event. The server has
# no controllers, so this no-ops there.

const DEFAULT_RADIUS := 0.10
# The controller origin sits at the grip; the visible fingers (and where the user
# expects the touch point) are ~this far forward (-Z). Detect from there so you don't
# have to overshoot the button with the grip.
const FINGER_REACH := 0.08

var _left: Node3D = null
var _right: Node3D = null
var _inside: Dictionary = {}     # "side|node_path" -> bool (was the hand inside last frame)

func _ready() -> void:
	_left = get_node_or_null("../XROrigin3D/LeftController")
	_right = get_node_or_null("../XROrigin3D/RightController")

func _process(_dt: float) -> void:
	_scan("left", _left)
	_scan("right", _right)

func _scan(side: String, ctrl: Node3D) -> void:
	if ctrl == null:
		return
	# Detect from the fingertip (a bit forward of the grip), not the controller origin.
	var hp := ctrl.global_position - ctrl.global_transform.basis.z * FINGER_REACH
	for node in get_tree().get_nodes_in_group("hand_touch"):
		if not node.has_method("handle_global_position") or not node.has_method("activate"):
			continue
		var r := DEFAULT_RADIUS
		if node.has_method("press_radius"):
			r = node.press_radius()
		var inside: bool = hp.distance_to(node.handle_global_position()) <= r
		var key := side + "|" + str(node.get_path())
		if inside and not _inside.get(key, false):
			node.activate(side)
		_inside[key] = inside
