extends Node
# Controller locomotion WITH collision for VR.
# Lives at /root/HMVRGame/Locomotion in the client scene only (no XR on server).
#   Move hand thumbstick -> move (smooth) or aim teleport;  turn hand -> smooth/snap turn.
# Movement is routed through a CharacterBody3D "player body" (a capsule) using
# move_and_slide, so walls and stationary props stop you. Loose RigidBodies you
# walk into get shoved aside. The rig (XROrigin3D) is then shifted so the head
# ends up over the body — if a wall stopped the body, the rig is held back too.
#
# F9 §4c.5 COMFORT: the move/turn hands (handedness), smooth-vs-snap turn, smooth-vs-
# teleport locomotion, the comfort vignette, and a height/seated offset all come from the
# `Comfort` autoload (user-overridable, comfort-first defaults). Comfort absent -> the old
# smooth-locomotion behaviour, so nothing breaks if the autoload isn't present.

const MOVE_SPEED   := 3.0    # metres/sec at full stick deflection
const TURN_SPEED   := 2.5    # radians/sec at full stick deflection (smooth turn)
const DEADZONE     := 0.2
const BODY_RADIUS  := 0.22   # torso-height sphere — slides round edges, never wedges
const HEAD_DROP    := 0.60   # body centre sits this far below the head (keeps it off the floor)
const PUSH_IMPULSE := 2.5    # shove given to RigidBodies you walk into
const TOGGLE_ACTION := "by_button"   # B (right) / Y (left) toggles collision for debugging
const WALKABLE_MASK := 1 << 2   # collision layer 3 — floors/stair ramps (matches WALKABLE_LAYER in the converter)
const CLIMB_SPEED   := 3.0      # m/s the rig rises/descends to follow the floor/stairs beneath it
const MAX_STEP_UP   := 0.40     # ignore walkable surfaces more than this above us (overhead ramps/ledges) -> don't get yanked up when walking UNDER the stairs

# Comfort thresholds.
const SNAP_PRIME    := 0.7      # stick.x past this arms a snap turn; must fall below RESET first
const SNAP_RESET    := 0.3      # stick.x must drop below this before another snap fires
const TP_AIM        := 0.6      # forward stick push past this aims a teleport
const TP_RELEASE    := 0.25     # stick magnitude below this confirms (releases) the teleport
# Arc tuned to land INSIDE small rooms: a fast/flat arc sails over the floor and (since walls
# aren't on the walkable mask) passes through the wall finding no target. Slower launch +
# stronger gravity drops it onto the floor a couple of metres ahead. A straight-down ray from
# the arc tip is also cast each step so aiming at your feet always finds the floor.
const TP_ARC_SPEED  := 4.5      # teleport arc launch speed (m/s)
const TP_ARC_G      := -18.0    # teleport arc gravity (m/s^2)
const TP_ARC_STEPS  := 40
const TP_ARC_DT     := 0.04
const TP_MAX_RANGE  := 8.0      # ignore landings further than this (keeps it sane in open scenes)
const SEATED_LIFT   := 0.45     # extra rig height when seated (so seated eye ~ standing eye)

@onready var origin: XROrigin3D = get_node_or_null("../XROrigin3D")
@onready var camera: XRCamera3D = get_node_or_null("../XROrigin3D/XRCamera3D")
@onready var left:   XRController3D = get_node_or_null("../XROrigin3D/LeftController")
@onready var right:  XRController3D = get_node_or_null("../XROrigin3D/RightController")

var _body: CharacterBody3D
# Collision on by default; press B/Y to fly through walls for debugging.
var collision_enabled := true
var _toggle_down := false

var _comfort: Node = null
var _vignette: Node = null
var _turn_primed := true           # snap-turn: ready to fire once stick returns to centre
var _aiming_tp := false            # teleport: currently aiming
var _tp_valid := false
var _tp_target := Vector3.ZERO
var _tp_marker: Node3D = null

func _ready() -> void:
	if origin == null or camera == null:
		return
	_comfort = get_node_or_null("/root/Comfort")
	_body = CharacterBody3D.new()
	_body.name = "PlayerBody"
	_body.add_to_group("player")   # F5: hazards detect the local player by this group
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
	_ensure_vignette()
	_ensure_tp_marker()

func _ensure_vignette() -> void:
	if camera == null:
		return
	_vignette = camera.get_node_or_null("ComfortVignette")
	if _vignette == null:
		_vignette = load("res://scripts/comfort_vignette.gd").new()
		(_vignette as Node).name = "ComfortVignette"
		camera.add_child(_vignette)

func _ensure_tp_marker() -> void:
	# A flat ring on the floor showing the teleport landing spot.
	_tp_marker = MeshInstance3D.new()
	_tp_marker.name = "TeleportMarker"
	var disc := CylinderMesh.new()
	disc.top_radius = 0.30
	disc.bottom_radius = 0.30
	disc.height = 0.02
	_tp_marker.mesh = disc
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(0.30, 0.85, 1.0, 0.7)
	m.emission_enabled = true
	m.emission = Color(0.30, 0.85, 1.0)
	_tp_marker.material_override = m
	_tp_marker.visible = false
	add_child(_tp_marker)

# Which controller moves / turns, from the handedness setting (Comfort absent -> left move).
func _move_ctrl() -> XRController3D:
	if _comfort and not _comfort.move_hand_is_left():
		return right
	return left

func _turn_ctrl() -> XRController3D:
	if _comfort and not _comfort.move_hand_is_left():
		return left
	return right

func _teleport_mode() -> bool:
	return _comfort != null and _comfort.locomotion_mode == "teleport"

func _snap_turn() -> bool:
	return _comfort == null or _comfort.turn_mode == "snap"

func _physics_process(dt: float) -> void:
	if _body == null:
		return
	_check_toggle()

	var move_intensity := 0.0
	if collision_enabled:
		# Lock the body to head height so the capsule always covers wall height.
		var by := camera.global_position.y - HEAD_DROP
		_body.global_position.y = by
		var head_xz := Vector3(camera.global_position.x, by, camera.global_position.z)

		var stick_vel := _stick_velocity()
		move_intensity = clampf(stick_vel.length() / MOVE_SPEED, 0.0, 1.0)
		# Follow the head (covers physical room-scale walking) + stick locomotion.
		var follow := (head_xz - _body.global_position) / dt
		_body.velocity = follow + stick_vel
		_body.move_and_slide()
		_push_bodies()

		# Shift the rig so the head sits over the body. A wall that stopped the
		# body also holds the rig back -> you cannot walk through walls.
		var shift := _body.global_position - head_xz
		origin.global_position += Vector3(shift.x, 0.0, shift.z)

		# Vertical traversal: probe straight down for the walkable surface under the
		# head and smoothly raise/lower the rig to stand on it (stairs / second floor).
		_follow_floor(dt)
	else:
		# Collision off (debug): free-fly, no blocking. Keep the body parked
		# under the head so re-enabling collision doesn't snap the rig.
		origin.global_position += _stick_velocity() * dt
		_body.global_position = Vector3(
			camera.global_position.x,
			camera.global_position.y - HEAD_DROP,
			camera.global_position.z)

	if _teleport_mode():
		_update_teleport()

	var turn_intensity := _apply_turn(dt)

	# Feed the comfort vignette: tunnel on while moving or turning smoothly.
	if _vignette:
		_vignette.set_motion(maxf(move_intensity, turn_intensity))

func _follow_floor(dt: float) -> void:
	# Downward ray on the walkable layer only -> ignores walls, the player's own body,
	# and grabbables (the gotcha that makes a naive floor-raycast hit the player sphere).
	var space := _body.get_world_3d().direct_space_state
	var from := camera.global_position + Vector3(0.0, 0.2, 0.0)
	var to := from + Vector3(0.0, -6.0, 0.0)
	var q := PhysicsRayQueryParameters3D.create(from, to, WALKABLE_MASK)
	q.exclude = [_body.get_rid()]
	var hit := space.intersect_ray(q)
	if hit:
		# Move the rig (player's feet) toward the surface at a fixed rate -> smooth
		# ascent up stairs/ramps, smooth descent. No hit (briefly over the stairwell
		# gap) -> leave Y unchanged so we never fall through the world.
		var cur: float = origin.global_position.y
		var target: float = hit.position.y + _height_offset()
		# Only follow surfaces within a step above us. A surface far higher is an
		# overhead ramp/ledge (e.g. walking UNDER the stairs) -> ignore it and stay
		# grounded; its underside collider blocks the body from passing through.
		if target - cur <= MAX_STEP_UP + _height_offset():
			origin.global_position.y = move_toward(cur, target, CLIMB_SPEED * dt)

func _height_offset() -> float:
	if _comfort == null:
		return 0.0
	return _comfort.height_offset + (SEATED_LIFT if _comfort.seated_mode else 0.0)

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
	# Smooth move only; in teleport mode the move stick aims instead of gliding.
	if _teleport_mode():
		return Vector3.ZERO
	var ctrl := _move_ctrl()
	if ctrl == null:
		return Vector3.ZERO
	var m := _deadzone(ctrl.get_vector2("primary"))
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

# Returns a 0..1 turn intensity (for the vignette). Smooth or snap per Comfort.
func _apply_turn(dt: float) -> float:
	var ctrl := _turn_ctrl()
	if ctrl == null:
		return 0.0
	var turn := _deadzone(ctrl.get_vector2("primary"))
	if _snap_turn():
		return _apply_snap_turn(turn.x)
	# Smooth turn.
	if turn.x == 0.0:
		return 0.0
	_rotate_rig(-turn.x * TURN_SPEED * dt)
	return clampf(absf(turn.x), 0.0, 1.0)

func _apply_snap_turn(x: float) -> float:
	# Fire one fixed-angle rotation per stick flick; require a return to centre between
	# flicks (debounce) so a held stick doesn't spin continuously.
	if _turn_primed and absf(x) >= SNAP_PRIME:
		var deg: float = _comfort.snap_turn_radians() if _comfort else deg_to_rad(45.0)
		_rotate_rig(-signf(x) * deg)
		_turn_primed = false
		return 1.0   # brief vignette blink on the snap
	if absf(x) < SNAP_RESET:
		_turn_primed = true
	return 0.0

func _rotate_rig(angle: float) -> void:
	var pivot := camera.global_position
	var offset := origin.global_position - pivot
	offset = offset.rotated(Vector3.UP, angle)
	origin.global_position = pivot + offset
	origin.rotate_y(angle)

# ── Teleport ──────────────────────────────────────────────────────────────────
func _update_teleport() -> void:
	var ctrl := _move_ctrl()
	if ctrl == null:
		return
	var m := ctrl.get_vector2("primary")
	if not _aiming_tp:
		if m.y >= TP_AIM:
			_aiming_tp = true
	else:
		if m.length() < TP_RELEASE:
			# Released — confirm.
			if _tp_valid:
				_do_teleport(_tp_target)
			_aiming_tp = false
			_tp_valid = false
			if _tp_marker:
				_tp_marker.visible = false
			return
		_aim_teleport(ctrl)

func _aim_teleport(ctrl: XRController3D) -> void:
	# Sample a parabolic arc from the controller; first walkable hit is the landing spot.
	var space := _body.get_world_3d().direct_space_state
	var pos := ctrl.global_position
	var vel := (-ctrl.global_transform.basis.z).normalized() * TP_ARC_SPEED
	_tp_valid = false
	for i in TP_ARC_STEPS:
		var nxt := pos + vel * TP_ARC_DT + Vector3(0, 0.5 * TP_ARC_G * TP_ARC_DT * TP_ARC_DT, 0)
		vel.y += TP_ARC_G * TP_ARC_DT
		var q := PhysicsRayQueryParameters3D.create(pos, nxt, WALKABLE_MASK)
		q.exclude = [_body.get_rid()]
		var hit := space.intersect_ray(q)
		if hit:
			var here := Vector3(camera.global_position.x, 0, camera.global_position.z)
			var there := Vector3(hit.position.x, 0, hit.position.z)
			if here.distance_to(there) <= TP_MAX_RANGE:
				_tp_target = hit.position
				_tp_valid = true
			break
		pos = nxt
	if _tp_marker:
		_tp_marker.visible = _tp_valid
		if _tp_valid:
			_tp_marker.global_position = _tp_target + Vector3(0, 0.02, 0)

func _do_teleport(target: Vector3) -> void:
	# Shift the rig so the camera's ground position lands on the target (keep facing).
	var head_xz := Vector3(camera.global_position.x, 0, camera.global_position.z)
	var tgt_xz := Vector3(target.x, 0, target.z)
	origin.global_position += (tgt_xz - head_xz)
	origin.global_position.y = target.y + _height_offset()
	if _vignette:
		_vignette.set_motion(1.0)   # brief blink masks the jump

func _deadzone(v: Vector2) -> Vector2:
	if v.length() < DEADZONE:
		return Vector2.ZERO
	return v
