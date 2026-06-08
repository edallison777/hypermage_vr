extends Node
# Drives lever/wheel Mechanisms from the VR controllers. Mirrors GrabManager's
# trigger-polling approach (robust on Quest) and its server-relay model:
# clients read input + move the mechanism; the server only relays values to peers.
# Lives at /root/HMVRGame/MechanismManager in both client and server scenes.

const ENGAGE_RADIUS := 0.60   # metres — how close your hand must be to the handle
const TRIGGER_ON    := 0.7    # squeeze past this to engage
const TRIGGER_OFF   := 0.3    # release below this to let go
const SEND_INTERVAL := 1.0 / 20.0

var _diag_t: float = 0.0

var _left:  Node3D = null
var _right: Node3D = null
var _engaged: Dictionary = {}                       # "left"|"right" -> Mechanism node
var _down: Dictionary = {"left": false, "right": false}
var _timer: float = 0.0
# Set true by vr_main in offline/local mode (no server peer).
var local_mode: bool = false

func _ready() -> void:
	_left  = get_node_or_null("../XROrigin3D/LeftController")
	_right = get_node_or_null("../XROrigin3D/RightController")
	print("MechanismManager: left=" + str(_left != null) + " right=" + str(_right != null))

func _process(delta: float) -> void:
	var lt := _trigger(_left)
	var rt := _trigger(_right)

	# Server has no controllers; it only relays. local_mode runs the logic offline.
	if multiplayer.is_server() and not local_mode:
		return

	_handle("left",  _left,  lt)
	_handle("right", _right, rt)

	# Throttled diagnostic: nearest-handle distance per hand (grep MECHDIAG).
	_diag_t += delta
	if _diag_t >= 1.5:
		_diag_t = 0.0
		_diag()

	if local_mode:
		return

	# Broadcast engaged mechanism values at 20 Hz so other players see them move.
	_timer += delta
	if _timer >= SEND_INTERVAL:
		_timer = 0.0
		for side in _engaged.keys():
			var m = _engaged[side]
			if is_instance_valid(m):
				rpc_id(1, "sync_value", str(m.get_path()), m.value)

func _trigger(ctrl: Node3D) -> float:
	return ctrl.get_float("trigger") if ctrl else -1.0

func _handle(side: String, ctrl: Node3D, trig: float) -> void:
	if not ctrl:
		return
	if trig >= TRIGGER_ON:
		# While the trigger is held, keep trying to latch onto the nearest handle
		# until one is in range (don't require being on it the instant you squeeze).
		_down[side] = true
		if not _engaged.has(side):
			var m := _nearest(ctrl.global_position)
			if m:
				_engaged[side] = m
				m.engage(ctrl.global_position)
				print("MechMgr: ", side, " engaged ", m.name, " value=", m.value)
	elif trig <= TRIGGER_OFF and _down[side]:
		_down[side] = false
		if _engaged.has(side):
			var m = _engaged[side]
			if is_instance_valid(m):
				m.release()
			_engaged.erase(side)

	if _engaged.has(side):
		var m = _engaged[side]
		if is_instance_valid(m):
			m.drive(ctrl.global_position)

func _diag() -> void:
	var n := get_tree().get_nodes_in_group("mechanism").size()
	var ld := _nearest_dist(_left)
	var rd := _nearest_dist(_right)
	print("MECHDIAG: mechs=", n, " Lnear=", snappedf(ld, 0.01), " Rnear=", snappedf(rd, 0.01),
		" Ltrig=", snappedf(_trigger(_left), 0.01), " Rtrig=", snappedf(_trigger(_right), 0.01),
		" engaged=", _engaged.size())

func _nearest_dist(ctrl: Node3D) -> float:
	if not ctrl:
		return -1.0
	var best := 999.0
	for m in get_tree().get_nodes_in_group("mechanism"):
		if m.has_method("handle_global_position"):
			best = minf(best, ctrl.global_position.distance_to(m.handle_global_position()))
	return best

func _nearest(hand: Vector3) -> Node3D:
	var best: Node3D = null
	var best_d := ENGAGE_RADIUS
	for m in get_tree().get_nodes_in_group("mechanism"):
		if m.has_method("handle_global_position"):
			var d := hand.distance_to(m.handle_global_position())
			if d < best_d:
				best_d = d
				best = m
	return best

# ── Server relay ──────────────────────────────────────────────────────────────

@rpc("any_peer", "unreliable")
func sync_value(object_path: String, v: float) -> void:
	if multiplayer.is_server():
		var s := multiplayer.get_remote_sender_id()
		for p in multiplayer.get_peers():
			if p != s:
				rpc_id(p, "sync_value", object_path, v)
		return
	var m := get_node_or_null(NodePath(object_path))
	if m and m.has_method("set_value_remote"):
		m.set_value_remote(v)
