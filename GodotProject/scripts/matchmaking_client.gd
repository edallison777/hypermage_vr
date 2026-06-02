extends Node

signal matchmaking_complete(ip_address: String, port: int)
signal matchmaking_failed(error: String)

const API_BASE       := "https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"
const POLL_INTERVAL  := 3.0
const TIMEOUT_SECS   := 120.0

var _id_token  := ""
var _player_id := ""
var _ticket_id := ""
var _polling   := false
var _poll_time := 0.0
var _elapsed   := 0.0
var _http: HTTPRequest

func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 15.0
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)

func start(id_token: String, player_id: String) -> void:
	_id_token  = id_token
	_player_id = player_id
	_ticket_id = ""
	_polling   = false
	_poll_time = 0.0
	_elapsed   = 0.0
	_post_start()

func _auth_headers() -> PackedStringArray:
	return PackedStringArray([
		"Authorization: Bearer " + _id_token,
		"Content-Type: application/json"
	])

func _post_start() -> void:
	var body := JSON.stringify({"playerId": _player_id})
	_http.request(API_BASE + "/matchmaking/start", _auth_headers(), HTTPClient.METHOD_POST, body)

func _get_status() -> void:
	_http.request(API_BASE + "/matchmaking/status/" + _ticket_id, _auth_headers(), HTTPClient.METHOD_GET)

func _process(delta: float) -> void:
	if not _polling:
		return
	_elapsed += delta
	if _elapsed >= TIMEOUT_SECS:
		_polling = false
		matchmaking_failed.emit("Timed out after " + str(TIMEOUT_SECS) + "s")
		return
	_poll_time += delta
	if _poll_time >= POLL_INTERVAL:
		_poll_time = 0.0
		_get_status()

func _on_request_completed(result: int, code: int, _hdrs: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		matchmaking_failed.emit("Network error code=" + str(result))
		return
	if code not in [200, 201]:
		matchmaking_failed.emit("Matchmaking HTTP " + str(code) + ": " + body.get_string_from_utf8())
		return
	var json = JSON.parse_string(body.get_string_from_utf8())
	if not json:
		matchmaking_failed.emit("Invalid JSON response")
		return
	# Start response — has ticketId, polling not yet started
	if json.has("ticketId") and not _polling:
		_ticket_id = json["ticketId"]
		print("MatchmakingClient: ticket=" + _ticket_id)
		# Immediately COMPLETED (joined existing session — no poll needed)
		if json.get("status") == "COMPLETED" and json.has("gameSessionConnectionInfo"):
			var conn: Dictionary = json.get("gameSessionConnectionInfo", {})
			var ip: String = conn.get("ipAddress", "")
			var port: int   = int(conn.get("port", 7777))
			if not ip.is_empty():
				matchmaking_complete.emit(ip, port)
				return
		_polling = true
		return
	# Poll response — has status
	var status: String = json.get("status", "")
	print("MatchmakingClient: status=" + status)
	match status:
		"COMPLETED":
			_polling = false
			var conn: Dictionary = json.get("gameSessionConnectionInfo", {})
			var ip: String = conn.get("ipAddress", "")
			var port: int   = int(conn.get("port", 7777))
			if ip.is_empty():
				matchmaking_failed.emit("COMPLETED but no ipAddress")
			else:
				matchmaking_complete.emit(ip, port)
		"FAILED":
			_polling = false
			matchmaking_failed.emit("Server error: " + json.get("statusReason", "unknown"))
		# SEARCHING / ecsStatus variants — keep polling
