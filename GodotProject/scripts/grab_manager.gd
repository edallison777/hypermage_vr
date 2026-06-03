extends Node
# Grab/throw system for VR controllers.
# Lives at /root/HMVRGame/GrabManager in both server and client scenes.
# Polls the analog trigger every frame (robust on Quest) instead of relying on
# button_pressed events, which don't always fire for a click action bound to
# the analog trigger/value path.
# Server acts as a relay only; clients handle all input and physics.

const GRAB_RADIUS   := 0.40   # metres — how close your hand must be
const TRIGGER_ON    := 0.7    # squeeze past this to grab
const TRIGGER_OFF   := 0.3    # release below this to throw
const THROW_MULT    := 2.5
const SEND_INTERVAL := 1.0 / 20.0

var _left:  Node3D = null
var _right: Node3D = null
var _held:  Dictionary = {}      # "left"|"right"  →  RigidBody3D
var _prev:  Dictionary = {}      # "left"|"right"  →  Vector3 (controller pos)
var _vel:   Dictionary = {}      # "left"|"right"  →  Vector3
var _down:  Dictionary = {"left": false, "right": false}
var _avatars_parent_ready := false
var _debug: Label3D = null
var _timer: float = 0.0
var _diag_timer: float = 0.0
# Set true by vr_main in offline/local mode (no server peer): run grab/throw
# locally and skip the relay RPCs that would fail without a connected peer.
var local_mode: bool = false

func _ready() -> void:
	# Cache scene refs unconditionally. is_server() is TRUE at startup (no peer yet),
	# so guarding here would skip caching and break grab after connecting.
	# On the headless server these nodes simply don't exist → null → input loop no-ops.
	_left  = get_node_or_null("../XROrigin3D/LeftController")
	_right = get_node_or_null("../XROrigin3D/RightController")
	_debug = get_node_or_null("../XROrigin3D/XRCamera3D/DebugLabel")
	print("GrabManager: left=" + str(_left != null) + " right=" + str(_right != null) + " debug=" + str(_debug != null))

func _diag_dump() -> void:
	# One-shot-ish diagnostic: what does Godot's XR system actually have?
	var iface := XRServer.find_interface("OpenXR")
	print("XRDIAG: openxr_iface=", iface != null, " initialized=", (iface.is_initialized() if iface else false))
	var names: Array = []
	for t in XRServer.get_trackers(2).keys():  # 2 = TRACKER_CONTROLLER
		names.append(str(t))
	print("XRDIAG: controller_trackers=", names)
	var lh := XRServer.get_tracker("left_hand")
	var rh := XRServer.get_tracker("right_hand")
	print("XRDIAG: left_hand tracker=", lh != null, " right_hand tracker=", rh != null)
	if lh:
		# Probe the tracker's poses by name directly — which (if any) have data?
		for pn in ["default", "default_pose", "aim", "aim_pose", "grip", "grip_pose", "palm_pose"]:
			var p = lh.get_pose(pn)
			if p != null:
				print("XRDIAG:   left pose '", pn, "' track=", p.has_tracking_data, " conf=", p.tracking_confidence)
		# Probe an input action directly on the tracker.
		print("XRDIAG:   left input trigger=", lh.get_input("trigger"), " grip=", lh.get_input("grip"))
	if _left:
		print("XRDIAG: LeftController tracker=", _left.tracker, " pose=", _left.pose,
			" active=", _left.get_is_active(), " hasTrack=", _left.get_has_tracking_data())

func _process(delta: float) -> void:
	# Throttled XR diagnostic dump every ~2s (logcat: grep XRDIAG).
	_diag_timer += delta
	if _diag_timer >= 2.0:
		_diag_timer = 0.0
		_diag_dump()

	var lt := _trigger_val(_left)
	var rt := _trigger_val(_right)

	# LOCAL diagnostic readout — runs every frame on the client BEFORE the server
	# guard, so controller input can be verified without matchmaking/connection.
	#   act/trk = get_is_active() / get_has_tracking_data()
	#   If A T shown but trig & grip both 0.00 -> input actions unbound (profile/binding).
	#   If "- -" shown -> controller not active/tracked (focus or pairing issue).
	if _debug:
		_debug.text = "L %s t%.2f g%.2f\nR %s t%.2f g%.2f\nnear %.2f held %d" % [
			_state(_left),  lt, _grip(_left),
			_state(_right), rt, _grip(_right),
			_nearest_dist(_left), _held.size()]

	# Grab/throw + state broadcast require an active client peer (server only relays).
	# local_mode bypasses this so grab/throw works offline with no matchmaking.
	if multiplayer.is_server() and not local_mode:
		return

	_handle_side("left",  _left,  lt, delta)
	_handle_side("right", _right, rt, delta)

	# Broadcast held-object positions at 20 Hz (skip entirely in offline local mode)
	if local_mode:
		return
	_timer += delta
	var broadcast := _timer >= SEND_INTERVAL
	if broadcast:
		_timer = 0.0
		for side in _held.keys():
			var obj: RigidBody3D = _held[side]
			if is_instance_valid(obj):
				rpc_id(1, "sync_held", str(obj.get_path()), obj.global_transform)

func _trigger_val(ctrl: Node3D) -> float:
	if not ctrl:
		return -1.0
	return ctrl.get_float("trigger")

func _grip(ctrl: Node3D) -> float:
	if not ctrl:
		return -1.0
	return ctrl.get_float("grip")

func _state(ctrl: Node3D) -> String:
	# "AT" = active + has tracking data; "-" for each missing; "null" if node absent.
	if not ctrl:
		return "null"
	var a := "A" if ctrl.get_is_active() else "-"
	var t := "T" if ctrl.get_has_tracking_data() else "-"
	return a + t

func _handle_side(side: String, ctrl: Node3D, trig: float, delta: float) -> void:
	if not ctrl:
		return
	# velocity tracking
	var pos := ctrl.global_position
	if _prev.has(side):
		_vel[side] = (pos - _prev[side]) / delta
	_prev[side] = pos

	var was_down: bool = _down[side]
	if trig >= TRIGGER_ON and not was_down:
		_down[side] = true
		_grab(side, ctrl)
	elif trig <= TRIGGER_OFF and was_down:
		_down[side] = false
		_throw(side)

	# keep held object glued to controller
	if _held.has(side):
		var obj: RigidBody3D = _held[side]
		if is_instance_valid(obj):
			obj.global_transform = ctrl.global_transform

func _grab(side: String, ctrl: Node3D) -> void:
	if _held.has(side):
		return
	var best: RigidBody3D = null
	var best_d := GRAB_RADIUS
	for obj in get_tree().get_nodes_in_group("grabbable"):
		if obj is RigidBody3D:
			var d := ctrl.global_position.distance_to(obj.global_position)
			if d < best_d:
				best_d = d
				best = obj
	if best:
		best.freeze = true
		_held[side] = best
		print("GrabManager: grabbed " + best.name + " @ " + str(snapped(best_d, 0.01)) + "m")

func _throw(side: String) -> void:
	if not _held.has(side):
		return
	var obj: RigidBody3D = _held[side]
	_held.erase(side)
	if not is_instance_valid(obj):
		return
	var vel: Vector3 = _vel.get(side, Vector3.ZERO) * THROW_MULT
	obj.freeze = false
	obj.linear_velocity  = vel
	obj.angular_velocity = Vector3.ZERO
	if not local_mode:
		rpc_id(1, "do_throw", str(obj.get_path()), obj.global_transform, vel)
	print("GrabManager: threw " + obj.name + " @ " + str(snapped(vel.length(), 0.1)) + " m/s")

# ── Server relay ──────────────────────────────────────────────────────────────

@rpc("any_peer", "unreliable")
func sync_held(object_path: String, xf: Transform3D) -> void:
	if multiplayer.is_server():
		var s := multiplayer.get_remote_sender_id()
		for p in multiplayer.get_peers():
			if p != s:
				rpc_id(p, "sync_held", object_path, xf)
		return
	var obj := get_node_or_null(NodePath(object_path))
	if obj is RigidBody3D:
		obj.freeze = true
		obj.global_transform = xf

@rpc("any_peer", "reliable")
func do_throw(object_path: String, xf: Transform3D, vel: Vector3) -> void:
	if multiplayer.is_server():
		var s := multiplayer.get_remote_sender_id()
		for p in multiplayer.get_peers():
			if p != s:
				rpc_id(p, "do_throw", object_path, xf, vel)
		return
	var obj := get_node_or_null(NodePath(object_path))
	if obj is RigidBody3D:
		obj.global_transform = xf
		obj.freeze           = false
		obj.linear_velocity  = vel
		obj.angular_velocity = Vector3.ZERO

func _nearest_dist(ctrl: Node3D) -> float:
	if not ctrl:
		return -1.0
	var best := 999.0
	for obj in get_tree().get_nodes_in_group("grabbable"):
		if obj is Node3D:
			best = min(best, ctrl.global_position.distance_to(obj.global_position))
	return best
