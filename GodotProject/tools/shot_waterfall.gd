# Hero-framed render of the waterfall scene for off-headset A/B iteration (needs a real GPU,
# NOT --headless). Stands a camera near the pool looking up at the falls so the tall subject
# fills the frame (screenshot_room.gd's fixed downward tilt buries it behind foreground grass).
#   godot.exe --xr-mode off --path . -s res://tools/shot_waterfall.gd -- [cam_z]
# Writes res://tools/_room_preview.png
extends SceneTree

const ROOM := "res://scenes/generated/waterfall.tscn"
var _frames := 0
var _placed := false
var _cam: Camera3D = null

func _initialize() -> void:
	get_root().size = Vector2i(1280, 720)
	var packed := load(ROOM) as PackedScene
	if packed == null:
		push_error("shot_waterfall: cannot load " + ROOM)
		quit(1)
		return
	get_root().add_child(packed.instantiate())
	_cam = Camera3D.new()
	get_root().add_child(_cam)

func _place() -> void:
	for n in get_root().get_children():
		if n is Camera3D and n != _cam:
			(n as Camera3D).current = false
	var cam_z := 3.0
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		cam_z = float(args[0])
	_cam.current = true
	_cam.fov = 70.0
	_cam.global_position = Vector3(0.0, 2.0, cam_z)
	_cam.look_at(Vector3(0.0, 3.4, -11.0), Vector3.UP)
	print("shot_waterfall: cam at ", _cam.global_position)

func _process(_d: float) -> bool:
	_frames += 1
	if not _placed:
		_place()
		_placed = true
		return false
	if _frames < 60:           # let sky/shadow settle + particles spin up
		return false
	var img := get_root().get_texture().get_image()
	if img == null:
		push_error("shot_waterfall: null viewport image")
		return true
	img.save_png("res://tools/_room_preview.png")
	print("shot_waterfall: wrote res://tools/_room_preview.png (%dx%d)" % [img.get_width(), img.get_height()])
	return true
