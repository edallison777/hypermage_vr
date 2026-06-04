extends Node
# Controller locomotion WITH collision for VR.
# Lives at /root/HMVRGame/Locomotion in the client scene only (no XR on server).
#   Left thumbstick  -> move; Right thumbstick -> smooth turn.
# Movement is routed through a CharacterBody3D "player body" (a capsule) using
# move_and_slide, so walls and stationary props stop you. Loose RigidBodies you
# walk into get shoved aside. The rig (XROrigin3D) is then shifted so the head
# ends up over the body — if a wall stopped the body, the rig is held back too.

const MOVE_SPEED   := 3.0    # metres/sec at full stick deflection
const TURN_SPEED   := 2.5    # radians/sec at full stick deflection
const DEADZONE     := 0.2
const BODY_RADIUS  := 0.22   # torso-height sphere — slides round edges, never wedges
const HEAD_DROP    := 0.60   # body centre sits this far below the head (keeps it off the floor)
const PUSH_IMPULSE := 2.5    # shove given to RigidBodies you walk into
const TOGGLE_ACTION := "by_button"   # B (right) / Y (left) toggles collision for debugging

@onready var origin: XROrigin3D = get_node_or_null("../XROrigin3D")
@onready var camera: XRCamera3D = get_node_or_null("../XROrigin3D/XRCamera3D")
@onready var left:   XRController3D = get_node_or_null("../XROrigin3D/LeftController")
@onready var right:  XRController3D = get_node_or_null("../XROrigin3D/RightController")

var _body: CharacterBody3D
# Collision on by default; press B/Y to fly through walls for debugging.
var collision_enabled := true
var _toggle_down := false

func _ready() -> void:
	if origin == null or camera == null:
		return
	_body = CharacterBody3D.new()
	_body.name = "PlayerBody"
	var col := CollisionShape3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = BODY_RADIUS
	col.shape = sphere
	_body.add_child(col)
	add_child(_body)
	_body.global_position = Vector3(
		camera.global_position.x,
		camera.global_position.y - HEAD_DROP,
		camera.global_position.z)

func _physics_process(dt: float) -> void:
	if _body == null:
		return
	_check_toggle()

	if collision_enabled:
		# Lock the body to head height so the capsule always covers wall height.
		var by := camera.global_position.y - HEAD_DROP
		_body.global_position.y = by
		var head_xz := Vector3(camera.global_position.x, by, camera.global_position.z)

		# Follow the head (covers physical room-scale walking) + stick locomotion.
		var follow := (head_xz - _body.global_position) / dt
		_body.velocity = follow + _stick_velocity()
		_body.move_and_slide()
		_push_bodies()

		# Shift the rig so the head sits over the body. A wall that stopped the
		# body also holds the rig back -> you cannot walk through walls.
		var shift := _body.global_position - head_xz
		origin.global_position += Vector3(shift.x, 0.0, shift.z)
	else:
		# Collision off (debug): free-fly, no blocking. Keep the body parked
		# under the head so re-enabling collision doesn't snap the rig.
		origin.global_position += _stick_velocity() * dt
		_body.global_position = Vector3(
			camera.global_position.x,
			camera.global_position.y - HEAD_DROP,
			camera.global_position.z)

	_apply_turn(dt)

func _check_toggle() -> void:
	var pressed := false
	if left and left.is_button_pressed(TOGGLE_ACTION):
		pressed = true
	if right and right.is_button_pressed(TOGGLE_ACTION):
		pressed = true
	if pressed and not _toggle_down:
		collision_enabled = not collision_enabled
		print("Locomotion: collision ", "ON" if collision_enabled else "OFF")
	_toggle_down = pressed

func _stick_velocity() -> Vector3:
	if left == null:
		return Vector3.ZERO
	var m := _deadzone(left.get_vector2("primary"))
	if m == Vector2.ZERO:
		return Vector3.ZERO
	var fwd := -camera.global_transform.basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	var rgt := camera.global_transform.basis.x
	rgt.y = 0.0
	rgt = rgt.normalized()
	var dir := (rgt * m.x) + (fwd * m.y)
	if dir.length() > 1.0:
		dir = dir.normalized()
	return dir * MOVE_SPEED

func _push_bodies() -> void:
	for i in _body.get_slide_collision_count():
		var c := _body.get_slide_collision(i)
		var col = c.get_collider()
		if col is RigidBody3D and not col.freeze:
			var d := -c.get_normal()
			d.y = 0.0
			if d.length() > 0.01:
				col.apply_central_impulse(d.normalized() * PUSH_IMPULSE)

func _apply_turn(dt: float) -> void:
	if right == null:
		return
	var turn := _deadzone(right.get_vector2("primary"))
	if turn.x == 0.0:
		return
	var pivot := camera.global_position
	var angle := -turn.x * TURN_SPEED * dt
	var offset := origin.global_position - pivot
	offset = offset.rotated(Vector3.UP, angle)
	origin.global_position = pivot + offset
	origin.rotate_y(angle)

func _deadzone(v: Vector2) -> Vector2:
	if v.length() < DEADZONE:
		return Vector2.ZERO
	return v
