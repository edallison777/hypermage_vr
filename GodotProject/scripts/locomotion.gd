extends Node
# Controller locomotion for VR.
# Lives at /root/HMVRGame/Locomotion in the client scene only (no XR on server).
#   Left thumbstick  (primary)  -> smooth move on the horizontal plane,
#                                  relative to where the head is looking.
#   Right thumbstick (primary)  -> smooth turn, pivoting around the head so the
#                                  player doesn't get shoved sideways when rotating.

const MOVE_SPEED   := 3.0    # metres/sec at full stick deflection
const TURN_SPEED   := 2.5    # radians/sec at full stick deflection
const DEADZONE     := 0.2    # ignore tiny stick drift

@onready var origin: XROrigin3D = get_node_or_null("../XROrigin3D")
@onready var camera: XRCamera3D = get_node_or_null("../XROrigin3D/XRCamera3D")
@onready var left:   XRController3D = get_node_or_null("../XROrigin3D/LeftController")
@onready var right:  XRController3D = get_node_or_null("../XROrigin3D/RightController")

func _process(delta: float) -> void:
	if origin == null or camera == null:
		return

	# ── Move: left stick ────────────────────────────────────────────────────
	if left:
		var move := _deadzone(left.get_vector2("primary"))
		if move != Vector2.ZERO:
			# Head-relative basis flattened onto the horizontal plane.
			var fwd := -camera.global_transform.basis.z
			fwd.y = 0.0
			fwd = fwd.normalized()
			var rgt := camera.global_transform.basis.x
			rgt.y = 0.0
			rgt = rgt.normalized()
			var dir := (rgt * move.x) + (fwd * move.y)
			origin.global_position += dir * MOVE_SPEED * delta

	# ── Turn: right stick ───────────────────────────────────────────────────
	if right:
		var turn := _deadzone(right.get_vector2("primary"))
		if turn.x != 0.0:
			# Rotate the origin about the head's vertical axis so the camera
			# stays put and only the facing direction changes.
			var pivot := camera.global_position
			var angle := -turn.x * TURN_SPEED * delta
			var offset := origin.global_position - pivot
			offset = offset.rotated(Vector3.UP, angle)
			origin.global_position = pivot + offset
			origin.rotate_y(angle)

func _deadzone(v: Vector2) -> Vector2:
	if v.length() < DEADZONE:
		return Vector2.ZERO
	return v
