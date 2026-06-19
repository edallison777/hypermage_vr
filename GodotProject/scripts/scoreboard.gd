extends Node3D
# In-world scoreboard (F6 — see GodotProject/FEATURE_PLAN.md). A converter-generated,
# wall-mountable panel that derives ENTIRELY from the GameState bus events — it owns no
# game state. Shows the shared team score, objective progress, the countdown (if any),
# and a WIN / LOSE banner. (F6b will add a top-N leaderboard section fed by the same node.)
#
# Objective TOTAL is read once from the "objective" group at _ready (the room's objectives
# exist by then); progress increments as objective:completed events arrive.

@export var board_title: String = "OBJECTIVES"

var _bus: Node = null
var _score := 0
var _done := 0
var _total := 0
var _time_left := -1
var _ended := false

var _score_lbl: Label3D = null
var _obj_lbl: Label3D = null
var _time_lbl: Label3D = null
var _banner_lbl: Label3D = null
var _lb_lbl: Label3D = null

func _ready() -> void:
	_total = get_tree().get_nodes_in_group("objective").size()
	_build()
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)
	_redraw()

func _mk_label(y: float, size: int, color: Color) -> Label3D:
	var l := Label3D.new()
	# Sit the text just IN FRONT of the 0.04 m-deep backing panel (front face at +0.02);
	# at z=0 the opaque panel occludes it (reads as a blank black screen).
	l.position = Vector3(0.0, y, 0.03)
	l.font_size = size
	l.pixel_size = 0.0015
	l.modulate = color
	l.outline_size = 6
	# Render the HUD text on top regardless of the panel depth, so it never clips.
	l.no_depth_test = true
	add_child(l)
	return l

func _build() -> void:
	var back := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = Vector3(1.4, 1.5, 0.04)
	back.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.04, 0.05, 0.08)
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	back.material_override = mat
	add_child(back)

	var title := _mk_label(0.64, 40, Color(0.7, 0.8, 1.0))
	title.text = board_title
	_score_lbl  = _mk_label(0.46, 48, Color(1, 1, 0.5))
	_obj_lbl    = _mk_label(0.30, 40, Color(1, 1, 1))
	_time_lbl   = _mk_label(0.14, 40, Color(0.8, 0.9, 0.8))
	_banner_lbl = _mk_label(-0.04, 52, Color(0.5, 1, 0.5))
	# Leaderboard (F6b): populated from "leaderboard:loaded"; multi-line, top-anchored.
	_lb_lbl = _mk_label(-0.20, 30, Color(0.85, 0.85, 0.95))
	_lb_lbl.vertical_alignment = VERTICAL_ALIGNMENT_TOP

func _on_event(name: String, payload: Dictionary) -> void:
	match name:
		"score:changed":
			_score = int(payload.get("score", _score))
		"objective:completed":
			_done += 1
		"game:time":
			_time_left = int(payload.get("left", _time_left))
		"game:won":
			_ended = true
			_score = int(payload.get("score", _score))
			_banner("VICTORY", Color(0.4, 1.0, 0.4))
			return
		"game:lost":
			_ended = true
			_banner("DEFEAT — " + str(payload.get("reason", "")), Color(1.0, 0.4, 0.4))
			return
		"leaderboard:loaded":
			_show_leaderboard(payload.get("entries", []))
			return
		_:
			return
	_redraw()

func _show_leaderboard(entries: Array) -> void:
	if _lb_lbl == null:
		return
	var lines := ["— LEADERBOARD —"]
	for e in entries:
		lines.append("%d. %s  %d" % [int(e.get("rank", 0)),
				str(e.get("displayName", "?")), int(e.get("score", 0))])
	_lb_lbl.text = "\n".join(lines)

func _banner(text: String, color: Color) -> void:
	if _banner_lbl:
		_banner_lbl.text = text
		_banner_lbl.modulate = color
	_redraw()

func _redraw() -> void:
	if _score_lbl:
		_score_lbl.text = "SCORE  %d" % _score
	if _obj_lbl:
		_obj_lbl.text = "Objectives  %d / %d" % [_done, _total]
	if _time_lbl:
		_time_lbl.text = ("Time  %d" % _time_left) if _time_left >= 0 else ""
