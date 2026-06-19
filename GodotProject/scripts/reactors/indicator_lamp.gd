extends "res://scripts/reactor.gd"
# Indicator lamp (F2): a reactor that toggles on/off when a specific interactable
# fires. Listens on `trigger_event` (e.g. "interact:button"); if `source_id` is set,
# reacts only to that interactable's id. On toggle it switches BOTH the cast light
# AND the bulb mesh's glow (emission), so the bulb itself reads as on/off — not just
# the light it throws. The in-world proof that interactable -> bus -> reactor works.

@export var source_id: String = ""
@export var light_path: NodePath = NodePath("Lamp")
@export var bulb_path: NodePath = NodePath("Bulb")
@export var glow_color: Color = Color(1.0, 0.6, 0.25)

var _on := false
var _bulb_mat: StandardMaterial3D = null

func _ready() -> void:
	super._ready()                      # reactor.gd: find bus + connect trigger_event
	var bulb := get_node_or_null(bulb_path)
	if bulb is MeshInstance3D:
		var m = bulb.get_active_material(0)
		_bulb_mat = (m.duplicate() if m is StandardMaterial3D else StandardMaterial3D.new())
		bulb.material_override = _bulb_mat
	_apply()                            # start in the off look (dark bulb, no light)

func _react(payload: Dictionary) -> void:
	if source_id != "" and str(payload.get("id", "")) != source_id:
		return
	_on = not _on
	_apply()

func _apply() -> void:
	var l := get_node_or_null(light_path)
	if l is Light3D:
		l.visible = _on
	if _bulb_mat:
		_bulb_mat.emission_enabled = _on
		_bulb_mat.emission = glow_color
		_bulb_mat.emission_energy_multiplier = 3.0 if _on else 0.0
		_bulb_mat.albedo_color = Color(1.0, 0.72, 0.42) if _on else Color(0.22, 0.20, 0.16)
