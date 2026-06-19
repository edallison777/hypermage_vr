extends Node3D
# Desktop, no-VR test harness for the F0 interaction framework. Run on the PC:
#   Godot_v4.6.3-stable_win64.exe --path . res://scenes/flat_test.tscn
#
# Loads a generated room (no XR rig), gives a free-fly camera, and lets you fire a
# discrete bus event from the keyboard to watch a Reactor respond — proving the
# bus -> reactor path end-to-end without a headset. Real F4 sequence / F5 health /
# F6 scoring logic can be exercised the same way.
#
# Controls:
#   W/A/S/D     move horizontally (camera-relative)
#   Q / E       move down / up
#   right-mouse hold + drag : look around
#   left-mouse  hold + drag up/down : drive the nearest lever/wheel (value 0..1),
#               so its value_changed reactions (e.g. the secret door) fire on the PC
#   T           fire "test:toggle_light" on the bus -> LightReactor toggles the lamp
#   G           play a one-shot 3D SFX at the camera (F1 audio check)
#   H / J       F5 health: take 20 damage / heal 20 (drives the wrist HUD)
#   K           F5: lethal hit -> death -> auto-respawn after the delay
#   Esc         quit
#
# F1 audio is also exercised passively: an ambient bed plays on start, and driving
# the lever (LMB) opens the secret door which plays its rumble.

const LightReactor = preload("res://scripts/reactors/light_reactor.gd")
const HealthManager = preload("res://scripts/health_manager.gd")
const HealthHUD = preload("res://scripts/health_hud.gd")
const GameState = preload("res://scripts/game_state.gd")
const ROOM_PATH := "res://scenes/generated/objective-test.tscn"
const MOVE_SPEED := 4.0
const LOOK_SENS := 0.005
const ENGAGE_RANGE := 4.0     # how close the camera must be to a mechanism handle
const DRIVE_SENS := 0.004     # value units per pixel of vertical drag

var _cam: Camera3D
var _bus: Node = null
var _yaw := 0.0
var _pitch := 0.0
var _looking := false
var _driving: Node = null     # mechanism currently being driven by the mouse
var _drive_value := 0.0
var _health: Node = null
var _game: Node = null

func _ready() -> void:
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.local_mode = true     # no peer in flat mode; emit locally
	else:
		push_warning("FlatHarness: no GameEvents bus (autoload missing?)")

	# Lit environment so geometry is visible (the generated rooms carry no sky/ambient).
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.06, 0.09)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.6, 0.6, 0.65)
	env.ambient_light_energy = 1.0
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	# Load the room so there's something to look at.
	var spawn := Vector3(0, 0, 1)
	var packed := load(ROOM_PATH) as PackedScene
	if packed:
		var room := packed.instantiate()
		room.name = "Room"
		add_child(room)
		# Stand at the room's spawn point; silence its baked-in PreviewCamera.
		for n in room.get_children():
			if n.name.begins_with("SpawnPoint"):
				spawn = (n as Node3D).global_position
			elif n is Camera3D:
				(n as Camera3D).current = false
	else:
		push_warning("FlatHarness: could not load room " + ROOM_PATH)

	# (Rooms now carry their own reactors — indicator lamps wired to the relevant
	# events — so the harness no longer adds a global proof lamp. The T key keeps a
	# bare bus->LightReactor smoke test on its own dim lamp for quick bus checks.)
	var lamp := OmniLight3D.new()
	lamp.name = "ProofLamp"
	lamp.position = Vector3(0, 3.2, 0)
	lamp.omni_range = 5.0
	lamp.light_energy = 2.0
	lamp.light_color = Color(0.4, 0.6, 1.0)
	lamp.visible = false
	add_child(lamp)
	var reactor := LightReactor.new()
	reactor.trigger_event = "test:toggle_light"     # only the T key, not gameplay events
	add_child(reactor)
	reactor.light_path = lamp.get_path()

	# Ground reference + sun so the scene is lit even if the room is dim.
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	add_child(sun)

	_cam = Camera3D.new()
	_cam.current = true
	# Eye height above the spawn, looking -Z (toward the secret door / vault).
	_cam.position = spawn + Vector3(0, 1.7, 0)
	add_child(_cam)

	Audio.play_ambient()       # F1: looping ambient bed

	# F5: a self-authoritative HealthManager + wrist HUD (parented to the camera in
	# flat mode). H/J/K drive damage/heal/death so the HUD and respawn loop can be
	# exercised on the PC. (Hazard auto-damage needs the VR player body, absent here.)
	_health = HealthManager.new()
	add_child(_health)
	_health.setup_offline()
	var hud := HealthHUD.new()
	_cam.add_child(hud)
	hud.position = Vector3(0.0, -0.18, -0.6)

	# F6: GameState authority (offline). begin() scans the room's objective/rules nodes,
	# so add it after the room is in the tree. Press buttons (F) to complete objectives;
	# the room's scoreboard reacts. K (lethal x4) exercises the death-cap lose.
	_game = GameState.new()
	add_child(_game)
	_game.setup_offline()

	print("FlatHarness: ready. WASD/QE move, RMB look, LMB-drag lever, F press nearest button/switch, T lamp, G sfx, H/J/K health, Esc quits.")

func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_RIGHT:
		_looking = e.pressed
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _looking else Input.MOUSE_MODE_VISIBLE
	elif e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_LEFT:
		if e.pressed:
			_driving = _nearest_mechanism()
			if _driving:
				_drive_value = _driving.value
				print("FlatHarness: driving ", _driving.name, " (drag up/down)")
		else:
			_driving = null
	elif e is InputEventMouseMotion:
		if _driving:
			_drive_value = clampf(_drive_value - e.relative.y * DRIVE_SENS, 0.0, 1.0)
			# set_value_remote applies the value and emits value_changed, so wired
			# reactions (the secret door) respond — the same path a remote peer uses.
			if _driving.has_method("set_value_remote"):
				_driving.set_value_remote(_drive_value)
		elif _looking:
			_yaw -= e.relative.x * LOOK_SENS
			_pitch = clampf(_pitch - e.relative.y * LOOK_SENS, -1.4, 1.4)
			_cam.rotation = Vector3(_pitch, _yaw, 0.0)
	elif e is InputEventKey and e.pressed and not e.echo:
		if e.keycode == KEY_T and _bus:
			_bus.fire("test:toggle_light", {})
			print("FlatHarness: fired test:toggle_light")
		elif e.keycode == KEY_G:
			Audio.play_3d("ui_click", _cam.global_position)
			print("FlatHarness: played ui_click")
		elif e.keycode == KEY_F:
			# Flat mode has no VR hands -> "press" the nearest button/switch directly.
			var n := _nearest_hand_touch()
			if n:
				n.activate("left")
				print("FlatHarness: activated ", n.name)
		elif e.keycode == KEY_H and _health:
			_health.apply_damage(_health.local_id(), 20, "test")
			print("FlatHarness: -20 HP")
		elif e.keycode == KEY_J and _health:
			_health.heal(_health.local_id(), 20)
			print("FlatHarness: +20 HP")
		elif e.keycode == KEY_K and _health:
			_health.apply_damage(_health.local_id(), 999, "test")
			print("FlatHarness: lethal hit -> respawn")
		elif e.keycode == KEY_ESCAPE:
			get_tree().quit()

func _nearest_hand_touch() -> Node:
	var best: Node = null
	var best_d := 999.0
	for n in get_tree().get_nodes_in_group("hand_touch"):
		if n.has_method("handle_global_position") and n.has_method("activate"):
			var d: float = _cam.global_position.distance_to(n.handle_global_position())
			if d < best_d:
				best_d = d
				best = n
	return best

func _nearest_mechanism() -> Node:
	var best: Node = null
	var best_d := ENGAGE_RANGE
	var cam_pos := _cam.global_position
	for m in get_tree().get_nodes_in_group("mechanism"):
		if m.has_method("handle_global_position"):
			var d: float = cam_pos.distance_to(m.handle_global_position())
			if d < best_d:
				best_d = d
				best = m
	return best

func _process(delta: float) -> void:
	var dir := Vector3.ZERO
	if Input.is_physical_key_pressed(KEY_W): dir -= _cam.global_transform.basis.z
	if Input.is_physical_key_pressed(KEY_S): dir += _cam.global_transform.basis.z
	if Input.is_physical_key_pressed(KEY_A): dir -= _cam.global_transform.basis.x
	if Input.is_physical_key_pressed(KEY_D): dir += _cam.global_transform.basis.x
	if Input.is_physical_key_pressed(KEY_E): dir += Vector3.UP
	if Input.is_physical_key_pressed(KEY_Q): dir += Vector3.DOWN
	if dir != Vector3.ZERO:
		_cam.global_position += dir.normalized() * MOVE_SPEED * delta
