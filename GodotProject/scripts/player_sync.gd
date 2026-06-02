extends Node
# Handles position replication for all players.
# Lives at /root/HMVRGame/PlayerSync in BOTH server and client scenes.
# Godot routes RPCs by node path, so matching names in both scenes is required.

const SEND_INTERVAL := 1.0 / 20.0  # 20 Hz

var _send_timer    := 0.0
var _is_connected  := false
var _sv_peers:   Array[int]    = []
var _avatars:    Dictionary    = {}  # peer_id -> Node3D  (client only)

var _camera: Node3D = null
var _lctrl:  Node3D = null
var _rctrl:  Node3D = null

# Called by server_main._ready() after ENet peer is live.
# On the client, called by vr_main after game_network reports connected.
func setup() -> void:
	if multiplayer.is_server():
		multiplayer.peer_connected.connect(_sv_peer_up)
		multiplayer.peer_disconnected.connect(_sv_peer_down)
	else:
		multiplayer.connected_to_server.connect(_cl_connected)

# ── Server ────────────────────────────────────────────────────────────────────

func _sv_peer_up(id: int) -> void:
	# Tell all existing peers about the newcomer
	for p in _sv_peers:
		rpc_id(p, "player_joined", id)
	# Tell the newcomer about everyone already here
	for p in _sv_peers:
		rpc_id(id, "player_joined", p)
	_sv_peers.append(id)
	print("PlayerSync: sv peer_up id=" + str(id) + " total=" + str(_sv_peers.size()))

func _sv_peer_down(id: int) -> void:
	_sv_peers.erase(id)
	for p in _sv_peers:
		rpc_id(p, "player_left", id)
	print("PlayerSync: sv peer_down id=" + str(id) + " remaining=" + str(_sv_peers.size()))

@rpc("any_peer", "unreliable")
func update_transform(head: Transform3D, lh: Transform3D, rh: Transform3D) -> void:
	if not multiplayer.is_server():
		return
	var sender := multiplayer.get_remote_sender_id()
	for p in _sv_peers:
		if p != sender:
			rpc_id(p, "recv_transform", sender, head, lh, rh)

# ── Client ────────────────────────────────────────────────────────────────────

func _cl_connected() -> void:
	_is_connected = true
	_camera = get_node_or_null("../XROrigin3D/XRCamera3D")
	_lctrl  = get_node_or_null("../XROrigin3D/LeftController")
	_rctrl  = get_node_or_null("../XROrigin3D/RightController")
	print("PlayerSync: cl connected camera=" + str(_camera != null))

func _process(delta: float) -> void:
	if not _is_connected or multiplayer.is_server() or not _camera:
		return
	_send_timer += delta
	if _send_timer < SEND_INTERVAL:
		return
	_send_timer = 0.0
	var lh := _lctrl.global_transform if _lctrl else Transform3D.IDENTITY
	var rh := _rctrl.global_transform if _rctrl else Transform3D.IDENTITY
	rpc_id(1, "update_transform", _camera.global_transform, lh, rh)

@rpc("authority", "reliable")
func player_joined(peer_id: int) -> void:
	if _avatars.has(peer_id):
		return
	var avatar := Node3D.new()
	avatar.set_script(load("res://scripts/remote_player.gd"))
	avatar.name = "RemotePlayer_" + str(peer_id)
	get_parent().add_child(avatar)
	_avatars[peer_id] = avatar
	print("PlayerSync: spawned avatar for peer " + str(peer_id))

@rpc("authority", "reliable")
func player_left(peer_id: int) -> void:
	if not _avatars.has(peer_id):
		return
	_avatars[peer_id].queue_free()
	_avatars.erase(peer_id)
	print("PlayerSync: removed avatar for peer " + str(peer_id))

@rpc("authority", "unreliable")
func recv_transform(peer_id: int, head: Transform3D, lh: Transform3D, rh: Transform3D) -> void:
	if not _avatars.has(peer_id):
		return
	_avatars[peer_id].update_transforms(head, lh, rh)
