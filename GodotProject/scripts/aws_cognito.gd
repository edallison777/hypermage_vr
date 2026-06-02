extends Node

signal auth_success(id_token: String, player_id: String)
signal auth_failed(error: String)

const CLIENT_ID := "2iinqhoja78kj1et6rcv28bjvf"
const ENDPOINT  := "https://cognito-idp.eu-west-1.amazonaws.com/"

var _http: HTTPRequest

func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 30.0
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)

func login(username: String, password: String) -> void:
	var body := JSON.stringify({
		"AuthFlow": "USER_PASSWORD_AUTH",
		"ClientId": CLIENT_ID,
		"AuthParameters": { "USERNAME": username, "PASSWORD": password }
	})
	var headers := PackedStringArray([
		"Content-Type: application/x-amz-json-1.1",
		"X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth"
	])
	var err := _http.request(ENDPOINT, headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		auth_failed.emit("HTTPRequest start error: " + str(err))

func _on_request_completed(result: int, code: int, _hdrs: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		auth_failed.emit("Network error code=" + str(result))
		return
	if code != 200:
		auth_failed.emit("Cognito HTTP " + str(code) + ": " + body.get_string_from_utf8())
		return
	var json = JSON.parse_string(body.get_string_from_utf8())
	if not json or not json.has("AuthenticationResult"):
		auth_failed.emit("Unexpected auth response")
		return
	var id_token: String = json["AuthenticationResult"]["IdToken"]
	var player_id := _sub_from_jwt(id_token)
	print("CognitoAuth: ok player_id=" + player_id)
	auth_success.emit(id_token, player_id)

func _sub_from_jwt(token: String) -> String:
	var parts := token.split(".")
	if parts.size() < 2:
		return ""
	var payload := parts[1]
	while payload.length() % 4 != 0:
		payload += "="
	var bytes := Marshalls.base64_to_raw(payload)
	var parsed = JSON.parse_string(bytes.get_string_from_utf8())
	return parsed.get("sub", "") if parsed else ""
