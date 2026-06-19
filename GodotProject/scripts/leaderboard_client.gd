extends Node
# Leaderboard client (F6b — see GodotProject/FEATURE_PLAN.md).
#
# On game end the CLIENT submits its own final (team) score to the session API with
# its Cognito id_token — POST /scores, which the post-score Lambda upserts as a high
# score (only if higher). The server has no Cognito identity, so the client is the
# right place to submit (matches the Lambda's claims model). Then it GETs the top-N
# and re-broadcasts it LOCALLY on the bus as "leaderboard:loaded" {entries} so the
# in-world scoreboard can render it.
#
# Skips gracefully when not configured (offline / no id_token) — like the audio and
# bridge integrations — so offline play and the flat harness are unaffected.

signal leaderboard_loaded(entries: Array)

const API_BASE := "https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev"
const TOP_N := 10

var _id_token := ""
var _http_submit: HTTPRequest
var _http_fetch: HTTPRequest

func _ready() -> void:
	_http_submit = HTTPRequest.new()
	_http_submit.timeout = 15.0
	add_child(_http_submit)
	_http_submit.request_completed.connect(_on_submit_done)
	_http_fetch = HTTPRequest.new()
	_http_fetch.timeout = 15.0
	add_child(_http_fetch)
	_http_fetch.request_completed.connect(_on_fetch_done)

# Called by vr_main once Cognito auth succeeds. Empty token => leaderboard disabled.
func configure(id_token: String) -> void:
	_id_token = id_token

func enabled() -> bool:
	return _id_token != ""

func _headers() -> PackedStringArray:
	return PackedStringArray([
		"Authorization: Bearer " + _id_token,
		"Content-Type: application/json",
	])

# Submit our final score (then fetch the refreshed board). No-op if not configured.
func submit(score: int, session_id := "") -> void:
	if not enabled():
		return
	var body := JSON.stringify({"score": score, "sessionId": session_id})
	var err := _http_submit.request(API_BASE + "/scores", _headers(), HTTPClient.METHOD_POST, body)
	if err != OK:
		push_warning("LeaderboardClient: submit request error " + str(err))

func fetch(limit := TOP_N) -> void:
	if not enabled():
		return
	var err := _http_fetch.request(API_BASE + "/leaderboard?limit=" + str(limit),
			_headers(), HTTPClient.METHOD_GET)
	if err != OK:
		push_warning("LeaderboardClient: fetch request error " + str(err))

func _on_submit_done(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code not in [200, 201]:
		push_warning("LeaderboardClient: submit failed result=%d code=%d %s"
				% [result, code, body.get_string_from_utf8()])
	# Whether or not the score was a new high, refresh the board.
	fetch()

func _on_fetch_done(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		push_warning("LeaderboardClient: fetch failed result=%d code=%d" % [result, code])
		return
	var json = JSON.parse_string(body.get_string_from_utf8())
	if typeof(json) != TYPE_DICTIONARY or not json.has("leaderboard"):
		push_warning("LeaderboardClient: bad leaderboard response")
		return
	var entries: Array = json["leaderboard"]
	leaderboard_loaded.emit(entries)
	# Re-broadcast locally so the in-world scoreboard (a bus listener) can render it.
	var bus := get_tree().get_first_node_in_group("game_events")
	if bus:
		bus.fire_local("leaderboard:loaded", {"entries": entries})
