extends Node

signal connected_to_server
signal connection_failed(reason: String)
signal peer_welcomed(assigned_id: int)

func connect_to_server(ip: String, port: int) -> void:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_client(ip, port)
	if err != OK:
		connection_failed.emit("ENet create_client error=" + str(err))
		return
	multiplayer.multiplayer_peer = peer
	multiplayer.connected_to_server.connect(_on_connected)
	multiplayer.connection_failed.connect(_on_failed)
	print("GameNetwork: connecting to " + ip + ":" + str(port))

func _on_connected() -> void:
	print("GameNetwork: connected id=" + str(multiplayer.get_unique_id()))
	connected_to_server.emit()

func _on_failed() -> void:
	print("GameNetwork: connection failed")
	connection_failed.emit("ENet connection timed out")

@rpc("authority", "call_remote", "reliable")
func sv_welcome(assigned_id: int) -> void:
	print("GameNetwork: welcomed assigned_id=" + str(assigned_id))
	peer_welcomed.emit(assigned_id)
