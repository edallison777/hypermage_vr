extends Node3D
const Diag = preload("res://scripts/debug_flags.gd")
# Keypad with a paired display (input-devices feature). A converter-generated console
# that builds its own keys + display procedurally. Two modes:
#   "numeric" — 0-9 and "." (floating-point entry), DEL, CLR, ENT
#   "letter"  — A-Z, SPACE, SHIFT (caps toggle), DEL, CLR, ENT
# Keys (keypad_key.gd, group "hand_touch") are poked with the fingertip by the existing
# InteractableManager and fire "keypad:key" {id, key} on the F0 bus. THIS node listens
# and accumulates, so the text derives identically on every peer from the server-
# sequenced key stream (co-op: everyone sees the same entry). ENT fires "keypad:entered"
# {id, value} LOCALLY (deterministically derived on each peer, like the F4 sequence solve)
# so a code-lock / puzzle reactor can consume it.

const KeypadKey = preload("res://scripts/interactables/keypad_key.gd")

const SP := 0.075            # key spacing (m)
const CAP := 0.058           # key cap side (m)
const FRONT_Z := 0.03        # keys sit this far in front of the panel face

@export var keypad_id: String = ""
@export var mode: String = "numeric"      # "numeric" | "letter"

signal entered(value: String)

var _text := ""
var _caps := false
var _bus: Node = null
var _display: Label3D = null

func _ready() -> void:
	add_to_group("keypad")
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)
	_build()
	_update_display()

# ── Layout ────────────────────────────────────────────────────────────────────────

func _rows() -> Array:
	if mode == "letter":
		return [
			["A", "B", "C", "D", "E", "F", "G"],
			["H", "I", "J", "K", "L", "M", "N"],
			["O", "P", "Q", "R", "S", "T", "U"],
			["V", "W", "X", "Y", "Z", " "],
			["shift", "back", "clear", "enter"],
		]
	return [
		["7", "8", "9"],
		["4", "5", "6"],
		["1", "2", "3"],
		[".", "0", "back"],
		["clear", "enter"],
	]

func _label_for(v: String) -> String:
	match v:
		"back":  return "DEL"
		"clear": return "CLR"
		"enter": return "ENT"
		"shift": return "SHF"
		" ":     return "SPC"
		_:       return v

func _build() -> void:
	var rows: Array = _rows()
	var max_cols := 0
	for r in rows:
		max_cols = maxi(max_cols, r.size())
	var width := max_cols * SP + 0.04
	var height := (rows.size() + 1) * SP + 0.06    # +1 row of space for the display

	var back := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(width, height, 0.04)
	back.mesh = bm
	var bmat := StandardMaterial3D.new()
	bmat.albedo_color = Color(0.08, 0.09, 0.12)
	bmat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	back.material_override = bmat
	add_child(back)

	# Display strip + label across the top.
	var top := height / 2.0
	var screen := MeshInstance3D.new()
	var sm := BoxMesh.new()
	sm.size = Vector3(width - 0.04, SP * 0.9, 0.01)
	screen.mesh = sm
	screen.position = Vector3(0, top - SP * 0.7, FRONT_Z)
	var smat := StandardMaterial3D.new()
	smat.albedo_color = Color(0.0, 0.12, 0.06)
	smat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	screen.material_override = smat
	add_child(screen)

	_display = Label3D.new()
	_display.position = Vector3(0, top - SP * 0.7, FRONT_Z + 0.01)
	_display.font_size = 48
	_display.pixel_size = 0.0011
	_display.modulate = Color(0.4, 1.0, 0.5)
	_display.outline_size = 4
	_display.no_depth_test = true
	add_child(_display)

	# Key grid (top-down), each row centred.
	var row_top := top - SP * 1.6
	for ri in rows.size():
		var row: Array = rows[ri]
		var row_w := row.size() * SP
		var x0 := -row_w / 2.0 + SP / 2.0
		for ci in row.size():
			_mk_key(str(row[ci]), x0 + ci * SP, row_top - ri * SP)

func _mk_key(value: String, lx: float, ly: float) -> void:
	var key := Node3D.new()
	key.set_script(KeypadKey)
	key.name = "Key_" + ("dot" if value == "." else ("space" if value == " " else value))
	key.position = Vector3(lx, ly, FRONT_Z)
	key.keypad_id = keypad_id
	key.key_value = value
	add_child(key)
	var cap := MeshInstance3D.new()
	cap.name = "Cap"
	var cm := BoxMesh.new()
	cm.size = Vector3(CAP, CAP, 0.02)
	cap.mesh = cm
	var special := value in ["back", "clear", "enter", "shift", " "]
	var cmat := StandardMaterial3D.new()
	cmat.albedo_color = Color(0.5, 0.35, 0.15) if special else Color(0.22, 0.24, 0.30)
	cap.material_override = cmat
	key.add_child(cap)
	var lbl := Label3D.new()
	lbl.text = _label_for(value)
	lbl.position = Vector3(0, 0, 0.02)
	lbl.font_size = 36
	lbl.pixel_size = 0.0009
	lbl.no_depth_test = true
	cap.add_child(lbl)

# ── Accumulation (pure logic — directly unit-tested) ───────────────────────────────

func _on_event(name: String, payload: Dictionary) -> void:
	if name == "keypad:key" and str(payload.get("id", "")) == keypad_id:
		_apply_key(str(payload.get("key", "")))

func _apply_key(key: String) -> void:
	match key:
		"back":
			_text = _text.substr(0, maxi(0, _text.length() - 1))
		"clear":
			_text = ""
		"shift":
			_caps = not _caps
		"enter":
			entered.emit(_text)
			if _bus:
				_bus.fire_local("keypad:entered", {"id": keypad_id, "value": _text})
			if Diag.ON:
				print("Keypad: ", keypad_id, " entered '", _text, "'")
		".":
			if mode == "numeric" and not _text.contains("."):
				_text += "."
		" ":
			_text += " "
		_:
			# A digit or a letter. Letters honour the caps toggle.
			if key.length() == 1 and key >= "A" and key <= "Z":
				_text += key if _caps else key.to_lower()
			else:
				_text += key
	_update_display()

func value() -> String:
	return _text

func caps() -> bool:
	return _caps

func _update_display() -> void:
	if _display == null:
		return
	var suffix := ""
	if mode == "letter" and _caps:
		suffix = " [CAPS]"
	_display.text = (_text if _text != "" else "_") + suffix
