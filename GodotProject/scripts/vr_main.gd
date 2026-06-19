extends Node3D

const AUTO_LOGIN_PATH := "user://AutoLogin.txt"

const HealthHUD = preload("res://scripts/health_hud.gd")

@onready var status_label:   Label3D = $StatusLabel
@onready var cognito:        Node    = $CognitoAuth
@onready var matchmaking:    Node    = $MatchmakingClient
@onready var game_network:   Node    = $GameNetwork
@onready var player_sync:    Node    = $PlayerSync
@onready var health:         Node    = $HealthManager

var _spawn_pos := Vector3.ZERO
var _hud: Node = null

func _ready() -> void:
	var xr = XRServer.find_interface("OpenXR")
	if xr and xr.initialize():
		get_viewport().use_xr = true
	else:
		push_warning("OpenXR not available -- desktop fallback")

	cognito.auth_success.connect(_on_auth_success)
	cognito.auth_failed.connect(_on_auth_failed)
	matchmaking.matchmaking_complete.connect(_on_matchmaking_complete)
	matchmaking.matchmaking_failed.connect(_on_matchmaking_failed)
	game_network.connected_to_server.connect(_on_connected)
	game_network.connection_failed.connect(_on_connection_failed)

	# F5: react to authoritative health results for OUR player (death / respawn).
	var bus := get_tree().get_first_node_in_group("game_events")
	if bus:
		bus.event.connect(_on_health_event)

	_try_auto_login()

const LOCAL_ROOM_PATH := "res://scenes/generated/health-test.tscn"

func _try_auto_login() -> void:
	if not FileAccess.file_exists(AUTO_LOGIN_PATH):
		# Offline mode: no matchmaking. Load a room locally so grab/throw can be
		# tested without a server (grab_manager runs in local_mode).
		_load_local_room()
		return
	var f := FileAccess.open(AUTO_LOGIN_PATH, FileAccess.READ)
	if not f:
		_set_status("Cannot read AutoLogin.txt (err=" + str(FileAccess.get_open_error()) + ")")
		return
	var username := f.get_line().strip_edges()
	var password := f.get_line().strip_edges()
	f.close()
	if username.is_empty() or password.is_empty():
		_set_status("AutoLogin.txt: line 1=username, line 2=password")
		return
	_set_status("Authenticating...")
	cognito.login(username, password)

func _load_local_room() -> void:
	var packed := load(LOCAL_ROOM_PATH) as PackedScene
	if packed == null:
		_set_status("Local room load failed:\n" + LOCAL_ROOM_PATH)
		return
	var room := packed.instantiate()
	room.name = "Room"
	add_child(room)
	# Stand the player at the room's spawn point so interactables are within reach.
	for child in room.get_children():
		if child.name.begins_with("SpawnPoint"):
			$XROrigin3D.global_position = child.global_position
			_spawn_pos = child.global_position
			print("VRMain: moved XROrigin to spawn ", child.global_position)
			break
	# Drop the rig onto the visual floor (the spawn marker's Y may float above the
	# room's actual floor geometry, which makes the world feel sunken).
	call_deferred("_snap_rig_to_floor")
	# Enable offline grab/throw + mechanisms (if those managers are in this scene).
	var gm := get_node_or_null("GrabManager")
	if gm:
		gm.local_mode = true
	var mm := get_node_or_null("MechanismManager")
	if mm:
		mm.local_mode = true
	# Offline: discrete events emit locally (no server peer to sequence them).
	var bus := get_tree().get_first_node_in_group("game_events")
	if bus:
		bus.local_mode = true
	# Offline: HealthManager is its own authority; register the lone local player.
	if health:
		health.setup_offline()
	_spawn_health_hud()
	var n := get_tree().get_nodes_in_group("grabbable").size()
	Audio.play_ambient()
	_set_status("Local room (offline)\n" + LOCAL_ROOM_PATH.get_file() + "\ngrabbables: " + str(n))
	await get_tree().create_timer(4.0).timeout
	if is_instance_valid(status_label):
		status_label.visible = false

const WALL_DIM := 0.30   # floor/wall thickness used by the converter

func _snap_rig_to_floor() -> void:
	# Read the floor geometry's height directly (a downward ray hits the player's
	# own locomotion collision sphere, not the floor). Floor box centre + half its
	# thickness = the top surface the player should stand on.
	var room := get_node_or_null("Room")
	if room == null:
		return
	var floor_node := _find_prefixed(room, "Floor_")
	if floor_node == null:
		print("VRMain: no Floor_ node to snap to")
		return
	var top: float = floor_node.global_position.y + WALL_DIM / 2.0
	var p: Vector3 = $XROrigin3D.global_position
	p.y = top
	$XROrigin3D.global_position = p
	print("VRMain: snapped rig to floor top y=", top)

func _find_prefixed(n: Node, prefix: String) -> Node:
	if n.name.begins_with(prefix):
		return n
	for c in n.get_children():
		var r := _find_prefixed(c, prefix)
		if r:
			return r
	return null

func _on_auth_success(id_token: String, player_id: String) -> void:
	_set_status("Finding server...")
	matchmaking.start(id_token, player_id)

func _on_auth_failed(error: String) -> void:
	_set_status("Auth failed:\n" + error)

func _on_matchmaking_complete(ip: String, port: int) -> void:
	_set_status("Connecting to\n" + ip + ":" + str(port) + "...")
	game_network.connect_to_server(ip, port)

func _on_matchmaking_failed(error: String) -> void:
	_set_status("Matchmaking failed:\n" + error)

func _on_connected() -> void:
	_set_status("Connected!")
	player_sync.setup()
	_spawn_health_hud()
	Audio.play_ambient()
	await get_tree().create_timer(3.0).timeout
	if is_instance_valid(status_label):
		status_label.visible = false

# ── F5 health: HUD + death/respawn ────────────────────────────────────────────────

func _spawn_health_hud() -> void:
	if _hud != null:
		return
	_hud = HealthHUD.new()
	# Wrist readout: parent under the left controller, tilted up toward the face.
	var left := get_node_or_null("XROrigin3D/LeftController")
	if left:
		left.add_child(_hud)
		(_hud as Node3D).position = Vector3(0.0, 0.04, 0.05)
		(_hud as Node3D).rotation_degrees = Vector3(-55.0, 0.0, 0.0)
	else:
		add_child(_hud)

func _on_health_event(name: String, payload: Dictionary) -> void:
	var local_id: int = health.local_id() if health else 1
	if int(payload.get("peer", -1)) != local_id:
		return
	if name == "health:died":
		_set_status("You died...\nrespawning")
	elif name == "health:respawned":
		# Move our rig back to a spawn point (the authority restored HP; we reposition).
		var sp := _spawn_pos if _spawn_pos != Vector3.ZERO else _find_spawn_position()
		$XROrigin3D.global_position = sp
		if is_instance_valid(status_label):
			status_label.visible = false

func _find_spawn_position() -> Vector3:
	var n := _find_prefixed(self, "SpawnPoint")
	return (n as Node3D).global_position if n is Node3D else $XROrigin3D.global_position

func _on_connection_failed(reason: String) -> void:
	_set_status("Connection failed:\n" + reason)

func _set_status(msg: String) -> void:
	print("VRMain: " + msg.replace("\n", " | "))
	if is_instance_valid(status_label):
		status_label.text = msg
		status_label.visible = true
