extends Node
# Picks one of the generated rooms at server startup and replicates the
# choice to each joining client so everyone renders the same space.
# Lives at /root/HMVRGame/RoomManager in both server and client scenes.

const AVAILABLE_ROOMS := [
	"res://scenes/generated/wizards-tower.tscn",
	"res://scenes/generated/ancient-dungeon.tscn",
	"res://scenes/generated/forest-clearing.tscn",
]

var _scene_path := ""
var _room: Node = null

# Called by server_main._ready() after ENet peer is live.
func setup() -> void:
	if not multiplayer.is_server():
		return
	_scene_path = AVAILABLE_ROOMS[randi() % AVAILABLE_ROOMS.size()]
	_load_room(_scene_path)
	print("RoomManager: server loaded " + _scene_path.get_file())

func tell_client_room(peer_id: int) -> void:
	rpc_id(peer_id, "room_ready", _scene_path)

@rpc("authority", "reliable")
func room_ready(scene_path: String) -> void:
	if multiplayer.is_server():
		return
	_load_room(scene_path)
	print("RoomManager: client loaded " + scene_path.get_file())

func _load_room(scene_path: String) -> void:
	if _room:
		_room.queue_free()
		_room = null
	var packed := load(scene_path) as PackedScene
	if not packed:
		push_error("RoomManager: failed to load " + scene_path)
		return
	_room = packed.instantiate()
	_room.name = "Room"
	get_parent().add_child(_room)
	_scene_path = scene_path
