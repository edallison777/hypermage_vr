extends Node3D
const Diag = preload("res://scripts/debug_flags.gd")
# Hidden writing (input-devices feature). Text that is invisible until a torch cone
# falls on it. Each frame it checks every ON torch (group "torch") and tests whether
# this surface lies inside that torch's cone (within range + half-angle). reveal_mode:
#   "latch"     — fades in while lit and STAYS visible once first discovered
#   "while_lit" — only visible while a cone is actually on it
#
# Detection is geometric (distance + cone angle), not physics, and is the pure part
# (point_in_cone) that's unit-tested. Place these on/just in front of a wall.

@export var text: String = ""
@export var reveal_mode: String = "latch"        # "latch" | "while_lit"
@export var writing_color: Color = Color(0.9, 0.85, 0.6)

const FADE_SPEED := 6.0

var _label: Label3D = null
var _alpha := 0.0
var _discovered := false

func _ready() -> void:
	add_to_group("hidden_writing")
	_label = Label3D.new()
	_label.text = text
	_label.font_size = 64
	_label.pixel_size = 0.004
	_label.outline_size = 8
	_label.modulate = Color(writing_color.r, writing_color.g, writing_color.b, 0.0)
	# The OUTLINE renders even when the fill alpha is 0, so it must be faded too —
	# otherwise the hidden text leaks through as an outline before it's discovered.
	_label.outline_modulate = Color(0, 0, 0, 0.0)
	_label.no_depth_test = true
	add_child(_label)

# Pure cone test: is `point` inside the cone from `origin` along `dir` (unit), within
# `range`, with half-angle whose cosine is `cos_half`? Unit-tested.
static func point_in_cone(point: Vector3, origin: Vector3, dir: Vector3,
		range: float, cos_half: float) -> bool:
	var to := point - origin
	var d := to.length()
	if d > range:
		return false
	if d < 0.0001:
		return true
	return (to / d).dot(dir) >= cos_half

func is_lit() -> bool:
	for t in get_tree().get_nodes_in_group("torch"):
		if not t.is_on():
			continue
		if point_in_cone(global_position, t.cone_origin(), t.cone_dir(),
				t.cone_range, t.cone_cos_half()):
			return true
	return false

func _process(delta: float) -> void:
	var lit := is_lit()
	if lit:
		_discovered = true
	var show := lit or (reveal_mode == "latch" and _discovered)
	var target := 1.0 if show else 0.0
	if not is_equal_approx(_alpha, target):
		_alpha = move_toward(_alpha, target, FADE_SPEED * delta)
		if _label:
			_label.modulate.a = _alpha
			_label.outline_modulate.a = _alpha
