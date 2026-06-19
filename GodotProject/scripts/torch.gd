extends RigidBody3D
const Diag = preload("res://scripts/debug_flags.gd")
# Torch / flashlight (input-devices feature). A grabbable (group "grabbable") held with
# the trigger via the existing grab_manager; the GRIP button toggles the beam while
# held (grab_manager stamps the held hand on the "held_by" meta so we know which
# controller's grip to read). When on it emits a SpotLight plus a thin, translucent,
# coloured CONE that points down the torch's -Z. hidden_writing.gd queries torches in
# group "torch" (via is_on() + the cone params) to reveal concealed text the cone covers.

@export var cone_color: Color = Color(0.5, 0.8, 1.0)
@export var cone_range: float = 5.0
@export var cone_angle_deg: float = 14.0

var _on := false
var _grip_down := false
var _spot: SpotLight3D = null
var _cone: MeshInstance3D = null

func _ready() -> void:
	add_to_group("torch")
	if not is_in_group("grabbable"):
		add_to_group("grabbable")
	_build_beam()
	_set_on(false)

func _build_beam() -> void:
	_spot = SpotLight3D.new()                 # emits along local -Z
	_spot.spot_range = cone_range
	_spot.spot_angle = cone_angle_deg
	_spot.light_color = cone_color
	_spot.light_energy = 4.0
	add_child(_spot)

	# A cone of translucent light: tip at the torch, widening to -Z. CylinderMesh runs
	# along +Y, so rotate +90° about X (+Y -> +Z) and offset by -range/2 so the zero-
	# radius tip lands at the torch origin and the wide end is `range` ahead (-Z).
	_cone = MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.0
	cm.bottom_radius = cone_range * tan(deg_to_rad(cone_angle_deg))
	cm.height = cone_range
	_cone.mesh = cm
	_cone.rotation_degrees = Vector3(90, 0, 0)
	_cone.position = Vector3(0, 0, -cone_range / 2.0)
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED      # visible from inside the cone too
	mat.albedo_color = Color(cone_color.r, cone_color.g, cone_color.b, 0.14)
	_cone.material_override = mat
	add_child(_cone)

func _process(_dt: float) -> void:
	var side := str(get_meta("held_by", ""))
	if side == "":
		if _on:
			_set_on(false)        # dropped -> off
		_grip_down = false
		return
	var ctrl := _controller_for(side)
	if ctrl == null:
		return
	var grip: float = ctrl.get_float("grip")
	if grip >= 0.7 and not _grip_down:
		_grip_down = true
		_set_on(not _on)
	elif grip <= 0.3:
		_grip_down = false

func _set_on(on: bool) -> void:
	_on = on
	if _spot:
		_spot.visible = on
	if _cone:
		_cone.visible = on
	if Diag.ON:
		print("Torch: ", "ON" if on else "OFF")

# ── Cone query API (used by hidden_writing) ────────────────────────────────────────

func is_on() -> bool:
	return _on

func cone_origin() -> Vector3:
	return global_position

func cone_dir() -> Vector3:
	return -global_transform.basis.z.normalized()

func cone_cos_half() -> float:
	return cos(deg_to_rad(cone_angle_deg))

func _controller_for(side: String) -> Node3D:
	var path := "left_hand" if side == "left" else "right_hand"
	for c in _find_controllers(get_tree().root, []):
		if c.tracker == path:
			return c
	return null

func _find_controllers(n: Node, acc: Array) -> Array:
	if n is XRController3D:
		acc.append(n)
	for c in n.get_children():
		_find_controllers(c, acc)
	return acc
