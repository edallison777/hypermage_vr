extends Node3D

const AUTO_LOGIN_PATH := "user://AutoLogin.txt"

@onready var status_label:   Label3D = $StatusLabel
@onready var cognito:        Node    = $CognitoAuth
@onready var matchmaking:    Node    = $MatchmakingClient
@onready var game_network:   Node    = $GameNetwork

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

	_try_auto_login()

func _try_auto_login() -> void:
	if not FileAccess.file_exists(AUTO_LOGIN_PATH):
		_set_status("No AutoLogin.txt\nPush with adb:\nadb shell run-as com.hypermage.godot\n  sh -c 'cat > .../files/AutoLogin.txt'")
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
	await get_tree().create_timer(3.0).timeout
	if is_instance_valid(status_label):
		status_label.visible = false

func _on_connection_failed(reason: String) -> void:
	_set_status("Connection failed:\n" + reason)

func _set_status(msg: String) -> void:
	print("VRMain: " + msg.replace("\n", " | "))
	if is_instance_valid(status_label):
		status_label.text = msg
		status_label.visible = true
