extends Node

const PORT              := 7777
const MAX_CLIENTS       := 16
const NO_CLIENT_TIMEOUT := 90.0   # quit if nobody ever connects
const EMPTY_SHUTDOWN    := 30.0   # watchdog: quit 30s after last peer leaves

var _connected_peers: Array[int] = []
var _idle_time:  float = 0.0
var _empty_time: float = 0.0
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
	# Children' _ready ran before us (child-first order); trigger deferred inits now
	$PlayerSync.setup()
	$RoomManager.setup()

func _process(delta: float) -> void:
	if not _ever_had_peer:
		_idle_time += delta
		if _idle_time >= NO_CLIENT_TIMEOUT:
			print("Server: no client after " + str(NO_CLIENT_TIMEOUT) + "s -- exit")
			get_tree().quit(0)
	elif _connected_peers.is_empty():
		_empty_time += delta
		if _empty_time >= EMPTY_SHUTDOWN:
			print("Server: empty for " + str(EMPTY_SHUTDOWN) + "s -- watchdog exit")
			get_tree().quit(0)
	else:
		_empty_time = 0.0

func _on_peer_connected(id: int) -> void:
	_ever_had_peer = true
	_empty_time    = 0.0
	_connected_peers.append(id)
	print("Server: peer_connected id=" + str(id) + " total=" + str(_connected_peers.size()))

func _on_peer_disconnected(id: int) -> void:
	_connected_peers.erase(id)
	print("Server: peer_disconnected id=" + str(id) + " remaining=" + str(_connected_peers.size()))
