extends Node3D
# Visual avatar for a remote player: red sphere head + two small hand spheres.
# Created entirely in code — no .tscn needed.

var _head: MeshInstance3D
var _lhand: MeshInstance3D
var _rhand: MeshInstance3D

func _ready() -> void:
	_head  = _sphere(0.11, Color(0.85, 0.30, 0.30))  # red head
	_lhand = _sphere(0.045, Color(0.30, 0.55, 0.90)) # blue left
	_rhand = _sphere(0.045, Color(0.30, 0.85, 0.50)) # green right

func _sphere(radius: float, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = radius
	sm.height = radius * 2.0
	mi.mesh = sm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mi.material_override = mat
	add_child(mi)
	return mi

func update_transforms(head: Transform3D, lh: Transform3D, rh: Transform3D) -> void:
	if _head:  _head.global_transform  = head
	if _lhand: _lhand.global_transform = lh
	if _rhand: _rhand.global_transform = rh
