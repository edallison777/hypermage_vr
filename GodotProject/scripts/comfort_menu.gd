extends Node3D
# World-space comfort/accessibility settings menu (F9 §4c.5). Part of the local rig (like
# the health HUD), NOT converter-generated. Toggle with the A/X button; a panel appears in
# front of you with one poke-button per setting that CYCLES its value (reusing the project's
# fingertip-poke interaction style). All changes are LOCAL (each player owns their comfort)
# and persisted by the `Comfort` autoload — deliberately off the networked event bus.
#
# Self-contained: it polls the controllers itself rather than going through
# InteractableManager, so a menu poke never becomes a server-sequenced game event.

const ROWS := [
	["locomotion_mode",   "Move"],
	["turn_mode",         "Turn"],
	["snap_degrees",      "Snap angle"],
	["locomotion_hand",   "Move hand"],
	["vignette_enabled",  "Vignette"],
	["vignette_strength", "Vignette amt"],
	["master_volume",     "Volume"],
	["height_offset",     "Height"],
	["seated_mode",       "Seated"],
	["captions_enabled",  "Captions"],
]

const ROW_H := 0.085
const POKE_RADIUS := 0.035
const FINGER_REACH := 0.08

@onready var camera: XRCamera3D = get_node_or_null("../XROrigin3D/XRCamera3D")
@onready var left:   XRController3D = get_node_or_null("../XROrigin3D/LeftController")
@onready var right:  XRController3D = get_node_or_null("../XROrigin3D/RightController")

var _comfort: Node = null
var _panel: Node3D = null
var _value_labels: Dictionary = {}     # key -> Label3D
var _button_nodes: Dictionary = {}     # key -> Node3D (poke target)
var _shown := false
var _toggle_down := false
var _inside: Dictionary = {}           # "side|key" -> bool

func _ready() -> void:
	if camera == null:
		return
	_comfort = get_node_or_null("/root/Comfort")
	_build_panel()
	visible = false
	if _comfort:
		_comfort.changed.connect(_refresh)

func _build_panel() -> void:
	_panel = Node3D.new()
	_panel.name = "Panel"
	add_child(_panel)
	var n := ROWS.size()
	var h := n * ROW_H + 0.16
	var w := 0.95
	# Backing.
	var back := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(w, h, 0.02)
	back.mesh = bm
	var bmat := StandardMaterial3D.new()
	bmat.albedo_color = Color(0.06, 0.07, 0.10, 0.92)
	bmat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	back.material_override = bmat
	_panel.add_child(back)
	# Title.
	var top := h / 2.0 - 0.06
	_panel.add_child(_make_label("COMFORT", Vector3(0, top, 0.02), 34, Color(0.7, 0.9, 1.0),
		HORIZONTAL_ALIGNMENT_CENTER))
	# Rows.
	for i in n:
		var key: String = ROWS[i][0]
		var nm: String = ROWS[i][1]
		var y := top - 0.09 - i * ROW_H
		_panel.add_child(_make_label(nm, Vector3(-w / 2.0 + 0.04, y, 0.02), 24,
			Color(0.85, 0.85, 0.9), HORIZONTAL_ALIGNMENT_LEFT))
		var vlabel := _make_label("", Vector3(0.12, y, 0.02), 24, Color(1, 1, 0.7),
			HORIZONTAL_ALIGNMENT_LEFT)
		_panel.add_child(vlabel)
		_value_labels[key] = vlabel
		# Poke button.
		var btn := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.025
		cm.bottom_radius = 0.025
		cm.height = 0.02
		btn.mesh = cm
		btn.rotation_degrees = Vector3(90, 0, 0)
		btn.position = Vector3(w / 2.0 - 0.06, y, 0.03)
		var cmat := StandardMaterial3D.new()
		cmat.albedo_color = Color(0.20, 0.55, 0.85)
		cmat.emission_enabled = true
		cmat.emission = Color(0.20, 0.55, 0.85)
		cmat.emission_energy_multiplier = 0.5
		btn.material_override = cmat
		_panel.add_child(btn)
		_button_nodes[key] = btn
	_refresh()

func _make_label(text: String, pos: Vector3, size: int, colour: Color,
		align: int) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.position = pos
	l.font_size = size
	l.pixel_size = 0.0011
	l.modulate = colour
	l.outline_size = 4
	l.horizontal_alignment = align
	l.no_depth_test = true
	return l

func _process(_dt: float) -> void:
	_check_toggle()
	if _shown:
		_scan_pokes("left", left)
		_scan_pokes("right", right)

func _check_toggle() -> void:
	var pressed := false
	if left and left.is_button_pressed("ax_button"):
		pressed = true
	if right and right.is_button_pressed("ax_button"):
		pressed = true
	if pressed and not _toggle_down:
		_toggle()
	_toggle_down = pressed

func _toggle() -> void:
	_shown = not _shown
	visible = _shown
	if _shown:
		_place_in_front()
		_refresh()

func _place_in_front() -> void:
	# Drop the panel ~1.1 m ahead at eye height, facing the player, level (ignore pitch/roll).
	var cam_xform := camera.global_transform
	var fwd := -cam_xform.basis.z
	fwd.y = 0.0
	if fwd.length() < 0.001:
		fwd = Vector3(0, 0, -1)
	fwd = fwd.normalized()
	var pos := cam_xform.origin + fwd * 1.1
	global_position = pos
	look_at(pos + fwd, Vector3.UP)

func _scan_pokes(side: String, ctrl: XRController3D) -> void:
	if ctrl == null:
		return
	var tip := ctrl.global_position - ctrl.global_transform.basis.z * FINGER_REACH
	for key in _button_nodes.keys():
		var btn: Node3D = _button_nodes[key]
		var inside: bool = tip.distance_to(btn.global_position) <= POKE_RADIUS
		var ik: String = side + "|" + str(key)
		if inside and not _inside.get(ik, false):
			_poke(key, ctrl)
		_inside[ik] = inside

func _poke(key: String, ctrl: XRController3D) -> void:
	if _comfort:
		_comfort.cycle(key)
	if Audio:
		Audio.play_3d("ui_click", (_button_nodes[key] as Node3D).global_position)
	if Haptics and ctrl:
		Haptics.pulse_controller(ctrl, 0.4, 0.05)
	_refresh()

func _refresh(_a := "", _b := {}) -> void:
	for key in _value_labels.keys():
		(_value_labels[key] as Label3D).text = _display(key, _comfort.get(key) if _comfort else null)

static func _display(key: String, value) -> String:
	# Human-readable value for the menu row.
	if value == null:
		return "-"
	if typeof(value) == TYPE_BOOL:
		return "ON" if value else "OFF"
	if typeof(value) == TYPE_FLOAT:
		if key == "snap_degrees":
			return "%d°" % int(round(value))
		if key == "master_volume" or key == "vignette_strength":
			return "%d%%" % int(round(value * 100.0))
		if key == "height_offset":
			return "%+.2fm" % value
		return str(value)
	return str(value).capitalize()
