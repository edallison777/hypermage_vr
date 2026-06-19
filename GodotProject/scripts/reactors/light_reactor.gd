extends "res://scripts/reactor.gd"
# Proof-of-F0 reactor: toggles a Light3D's visibility each time its trigger event
# fires. Used by the flat-mode harness to show an end-to-end bus -> reactor path on
# a desktop PC with no headset. A template for real F2+ reactors (doors, platforms).

@export var light_path: NodePath

func _react(_payload: Dictionary) -> void:
	var l := get_node_or_null(light_path)
	if l is Light3D:
		l.visible = not l.visible
