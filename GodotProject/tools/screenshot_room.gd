# Render a generated room to a PNG so the F9 runtime-lit look can be eyeballed off-headset.
# Needs a REAL rendering context (NOT --headless): the PC desktop GPU renders the sky,
# shadow and reflection probe that the headless dummy driver cannot.
#   godot.exe --xr-mode off --path . -s res://tools/screenshot_room.gd -- <res://room.tscn>
# Writes res://tools/_room_preview.png (and a copy under user://).
extends SceneTree

var _frames := 0
var _room_path := "res://scenes/generated/forest-clearing.tscn"
var _err := ""

func _initialize() -> void:
	# Pull the room path from the args after a bare "--", if given.
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_room_path = args[0]
	get_root().size = Vector2i(1280, 720)
	var packed := load(_room_path) as PackedScene
	if packed == null:
		_err = "could not load " + _room_path
		return
	var room := packed.instantiate()
	get_root().add_child(room)
	# Silence the editor PreviewCamera (it looks down from outside) and stand a camera at
	# player eye height inside the room, looking roughly horizontally — the VR-like view
	# that actually exercises sky-ambient, the sun shadow, fog depth and the materials.
	var spawn := Vector3(0, 0, 0)
	for n in room.get_children():
		if n is Camera3D:
			(n as Camera3D).current = false
		elif n.name.begins_with("SpawnPoint"):
			spawn = (n as Node3D).global_position
	var cam := Camera3D.new()
	get_root().add_child(cam)
	cam.current = true
	var eye := spawn + Vector3(0, 1.6, 0)
	cam.global_position = eye
	# Look across the room (toward -Z) with a slight downward tilt so floor+walls+ceiling
	# are all in frame.
	cam.look_at(eye + Vector3(0, -0.25, -1), Vector3.UP)

func _process(_d: float) -> bool:
	if _err != "":
		push_error("screenshot_room: " + _err)
		return true
	_frames += 1
	# Let the sky, the directional shadow and the ONCE reflection-probe bake settle.
	if _frames < 50:
		return false
	var img := get_root().get_texture().get_image()
	if img == null:
		push_error("screenshot_room: null viewport image (no render context?)")
		return true
	img.save_png("res://tools/_room_preview.png")
	img.save_png("user://_room_preview.png")
	print("screenshot_room: wrote res://tools/_room_preview.png (%dx%d)" % [img.get_width(), img.get_height()])
	return true
