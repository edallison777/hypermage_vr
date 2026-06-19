extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Client weapon handling (F7 — see GodotProject/FEATURE_PLAN.md). Lives at
# /root/HMVRGame/WeaponManager. The trigger is already the grab input (grab_manager),
# so weapons use the natural VR-shooter split instead:
#   GRIP   — equip the nearest weapon to that hand / holster the held one
#   TRIGGER — fire the equipped weapon
# Firing is predicted locally (muzzle flash + tracer + impact spark + SFX + haptic);
# the authoritative hit/damage is resolved by combat_manager (server or, offline,
# local). Weapons are in group "weapon" (not "grabbable") so grab_manager ignores them.

const GRIP_ON       := 0.7
const GRIP_OFF      := 0.3
const TRIGGER_ON    := 0.6
const TRIGGER_OFF   := 0.3
const EQUIP_RADIUS  := 0.45
const TRACER_LIFE   := 0.06
const FLASH_LIFE    := 0.05

var local_mode := false

var _left: Node3D = null
var _right: Node3D = null
var _equipped: Dictionary = {}                          # side -> weapon node
var _grip_down := {"left": false, "right": false}
var _trig_down := {"left": false, "right": false}
var _combat: Node = null

func _ready() -> void:
	_left  = get_node_or_null("../XROrigin3D/LeftController")
	_right = get_node_or_null("../XROrigin3D/RightController")

func _process(_delta: float) -> void:
	# Input only on the client (server has no controllers); local_mode bypasses the guard.
	if multiplayer.is_server() and not local_mode:
		return
	_handle_side("left", _left)
	_handle_side("right", _right)

func _handle_side(side: String, ctrl: Node3D) -> void:
	if ctrl == null:
		return
	var grip: float = ctrl.get_float("grip")
	var trig: float = ctrl.get_float("trigger")

	# GRIP rising edge: equip nearest / holster current.
	if grip >= GRIP_ON and not _grip_down[side]:
		_grip_down[side] = true
		if _equipped.has(side):
			_holster(side)
		else:
			_equip(side, ctrl)
	elif grip <= GRIP_OFF:
		_grip_down[side] = false

	# Keep an equipped weapon glued to the controller.
	if _equipped.has(side):
		var w = _equipped[side]
		if is_instance_valid(w):
			w.global_transform = ctrl.global_transform
		else:
			_equipped.erase(side)
			return

	# TRIGGER rising edge: fire.
	if trig >= TRIGGER_ON and not _trig_down[side]:
		_trig_down[side] = true
		if _equipped.has(side):
			_fire(side, ctrl)
	elif trig <= TRIGGER_OFF:
		_trig_down[side] = false

func _equip(side: String, ctrl: Node3D) -> void:
	var best: Node = null
	var best_d := EQUIP_RADIUS
	for w in get_tree().get_nodes_in_group("weapon"):
		if str(w.equipped_by) != "":
			continue
		var d: float = ctrl.global_position.distance_to((w as Node3D).global_position)
		if d < best_d:
			best_d = d
			best = w
	if best:
		_equipped[side] = best
		best.equipped_by = side
		Audio.play_3d("grab", best.global_position, -2.0)
		Haptics.pulse(side, 0.5, 0.05)
		if Diag.ON:
			print("WeaponManager: equipped ", best.weapon_id, " to ", side)

func _holster(side: String) -> void:
	var w = _equipped.get(side)
	_equipped.erase(side)
	if not is_instance_valid(w):
		return
	w.equipped_by = ""
	# Park it at the player's hip so it can be re-gripped (simple holster; tune on device).
	var cam := get_node_or_null("../XROrigin3D/XRCamera3D")
	if cam:
		var t: Transform3D = (cam as Node3D).global_transform
		w.global_position = t.origin - Vector3(0, 0.5, 0) + t.basis.x * 0.2
	Haptics.pulse(side, 0.3, 0.05)

func _fire(side: String, ctrl: Node3D) -> void:
	var w = _equipped[side]
	var muzzle: Transform3D = w.muzzle_transform()
	var origin := muzzle.origin
	var dir := -muzzle.basis.z.normalized()
	if not w.fire_consume():
		Audio.play_3d("ui_click", origin, -6.0, 0.6)   # dry click on empty
		Haptics.pulse(side, 0.15, 0.04)
		return
	# Predicted visuals + feedback (authoritative damage comes back via the bus).
	var endpoint := _visual_endpoint(origin, dir, w.fire_range)
	_spawn_tracer(origin, endpoint)
	_spawn_flash(origin, Color(1.0, 0.85, 0.4), 6.0)
	_spawn_flash(endpoint, Color(1.0, 0.6, 0.2), 3.0)
	Audio.play_3d("shot", origin, 0.0)
	Haptics.pulse(side, 0.85, 0.06)
	if _combat == null:
		_combat = get_tree().get_first_node_in_group("combat")
	if _combat:
		_combat.request_fire(origin, dir, int(w.damage))

# Client-side raycast purely to find where the tracer should END (visual only).
func _visual_endpoint(origin: Vector3, dir: Vector3, dist: float) -> Vector3:
	var world := get_viewport().world_3d
	if world == null:
		return origin + dir * dist
	var q := PhysicsRayQueryParameters3D.create(origin, origin + dir * dist)
	q.collide_with_areas = false
	var excl: Array[RID] = []
	for p in get_tree().get_nodes_in_group("player"):
		if p is CollisionObject3D:
			excl.append(p.get_rid())
	q.exclude = excl
	var hit := world.direct_space_state.intersect_ray(q)
	return hit.position if not hit.is_empty() else origin + dir * dist

func _spawn_tracer(a: Vector3, b: Vector3) -> void:
	var mesh := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	var len := a.distance_to(b)
	cyl.top_radius = 0.01
	cyl.bottom_radius = 0.01
	cyl.height = maxf(len, 0.01)
	mesh.mesh = cyl
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1.0, 0.9, 0.5)
	mesh.material_override = m
	_attach_world(mesh)
	# CylinderMesh runs along +Y; orient it along the shot and centre it.
	var mid := (a + b) * 0.5
	mesh.global_position = mid
	if len > 0.001:
		mesh.look_at_from_position(mid, b, Vector3.UP if absf(( b - a).normalized().dot(Vector3.UP)) < 0.99 else Vector3.RIGHT)
		mesh.rotate_object_local(Vector3.RIGHT, PI / 2.0)   # -Z (look_at) -> +Y (cylinder axis)
	_free_after(mesh, TRACER_LIFE)

func _spawn_flash(pos: Vector3, color: Color, energy: float) -> void:
	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = energy
	light.omni_range = 2.5
	_attach_world(light)
	light.global_position = pos
	_free_after(light, FLASH_LIFE)

func _attach_world(n: Node3D) -> void:
	# Parent VFX to the rig root (a Node3D) so positions are world-space and stable.
	var host := get_parent()
	if host is Node3D:
		host.add_child(n)
	else:
		get_tree().root.add_child(n)

func _free_after(n: Node, life: float) -> void:
	get_tree().create_timer(life).timeout.connect(func() -> void:
		if is_instance_valid(n):
			n.queue_free())
