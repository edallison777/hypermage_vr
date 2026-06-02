extends Node

const PORT := 7777
const MAX_CLIENTS := 16
const NO_CLIENT_TIMEOUT_SECS := 90.0

var _connected_peers: Array[int] = []
var _idle_time: float = 0.0
var _ever_had_peer: bool = false

func _ready() -> void:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_server(PORT, MAX_CLIENTS)
	if err != OK:
		push_error("Server: create_server failed err=" + str(err))
		get_tree().quit(1)
		return
	multiplayer.multiplayer_peer = peer
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	print("Server: listening port=" + str(PORT))

func _process(delta: float) -> void:
	if not _ever_had_peer:
		_idle_time += delta
		if _idle_time >= NO_CLIENT_TIMEOUT_SECS:
			print("Server: no client after " + str(NO_CLIENT_TIMEOUT_SECS) + "s -- exit")
			get_tree().quit(0)

func _on_peer_connected(id: int) -> void:
	_ever_had_peer = true
	_idle_time = 0.0
	_connected_peers.append(id)
	print("Server: peer_connected id=" + str(id) + " total=" + str(_connected_peers.size()))
	rpc_id(id, "sv_welcome", id)

func _on_peer_disconnected(id: int) -> void:
	_connected_peers.erase(id)
	print("Server: peer_disconnected id=" + str(id) + " remaining=" + str(_connected_peers.size()))
	if _ever_had_peer and _connected_peers.is_empty():
		print("Server: all peers gone -- exit")
		get_tree().quit(0)

@rpc("authority", "call_remote", "reliable")
func sv_welcome(assigned_id: int) -> void:
	pass  # stub -- handled client-side
