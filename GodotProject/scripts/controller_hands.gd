extends Node
# Visible hands for the local player's controllers.
# Lives at /root/HMVRGame/ControllerHands in the client scene only.
# Builds a simple stylized hand (palm + finger block + thumb) under each
# XRController3D so it inherits the controller pose automatically — no per-frame
# code. Colours match remote_player.gd (blue left / green right) so your own
# hands look the same as how other players see you.

# Per-hand transform offset to align the model with the OpenXR grip pose.
# Tune here if the hands look rotated/offset on device.
const HAND_OFFSET := Vector3(0.0, 0.0, -0.03)   # nudge forward toward fingers
const HAND_TILT_DEG := -25.0                     # tilt fingers down from the grip axis

const COL_LEFT  := Color(0.30, 0.55, 0.90)
const COL_RIGHT := Color(0.30, 0.85, 0.50)

func _ready() -> void:
	var left  := get_node_or_null("../XROrigin3D/LeftController")
	var right := get_node_or_null("../XROrigin3D/RightController")
	if left:
		_build_hand(left, COL_LEFT, true)
	if right:
		_build_hand(right, COL_RIGHT, false)

func _build_hand(controller: Node3D, color: Color, is_left: bool) -> void:
	# Root that carries the alignment offset; children are positioned relative to it.
	var root := Node3D.new()
	root.name = "HandModel"
	root.transform = Transform3D(Basis(Vector3.RIGHT, deg_to_rad(HAND_TILT_DEG)), HAND_OFFSET)
	controller.add_child(root)

	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.8

	# Palm — flattened ellipsoid.
	var palm := _mesh(root, mat)
	var palm_sphere := SphereMesh.new()
	palm_sphere.radius = 0.04
	palm_sphere.height = 0.08
	palm.mesh = palm_sphere
	palm.scale = Vector3(1.1, 0.45, 1.25)

	# Fingers — a rounded block reaching forward (-Z) from the palm.
	var fingers := _mesh(root, mat)
	var fbox := BoxMesh.new()
	fbox.size = Vector3(0.075, 0.022, 0.07)
	fingers.mesh = fbox
	fingers.position = Vector3(0.0, 0.0, -0.06)

	# Thumb — small capsule on the inner side, angled up.
	var thumb := _mesh(root, mat)
	var tcap := CapsuleMesh.new()
	tcap.radius = 0.013
	tcap.height = 0.05
	thumb.mesh = tcap
	var side := -1.0 if is_left else 1.0   # thumb points toward the body's centre
	thumb.position = Vector3(side * 0.035, 0.0, -0.02)
	thumb.rotation = Vector3(deg_to_rad(90.0), 0.0, deg_to_rad(side * 35.0))

func _mesh(parent: Node3D, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.material_override = mat
	parent.add_child(mi)
	return mi
