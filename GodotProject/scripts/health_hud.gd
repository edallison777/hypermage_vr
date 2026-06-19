extends Node3D
# Player health HUD (F5 — see GodotProject/FEATURE_PLAN.md).
#
# A small world-space panel — a coloured bar that shrinks green→red as HP drops, plus
# a numeric label. It is NOT converter-generated: like locomotion / grab_manager it is
# part of the local player's rig, not shared room content, so vr_main (VR: parented to
# the LeftController as a wrist readout) and the flat harness (parented to the camera)
# add it at runtime. It owns no HP — it just listens to the GameEvents bus for the
# LOCAL player's authoritative health and redraws.
#
# Defaults to full HP so a join race (the server's register broadcast arriving before
# this node connects) reads correctly: fresh players are at full HP anyway.

const BAR_W := 0.16     # full-health bar width (m)
const BAR_H := 0.025
const BAR_D := 0.004

var _bus: Node = null
var _bar: MeshInstance3D = null
var _bar_mat: StandardMaterial3D = null
var _label: Label3D = null
var _max := 100
var _hp := 100

func _ready() -> void:
	_build()
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_bus_event)
	_redraw()

func _local_id() -> int:
	return multiplayer.get_unique_id() if multiplayer.has_multiplayer_peer() else 1

func _build() -> void:
	# Dark backing plate.
	var back := MeshInstance3D.new()
	var back_mesh := BoxMesh.new()
	back_mesh.size = Vector3(BAR_W + 0.012, BAR_H + 0.012, BAR_D * 0.5)
	back.mesh = back_mesh
	var back_mat := StandardMaterial3D.new()
	back_mat.albedo_color = Color(0.05, 0.05, 0.06)
	back_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	back.material_override = back_mat
	add_child(back)

	# Foreground fill bar (left-anchored: pivot child shifts so it shrinks from the right).
	var pivot := Node3D.new()
	pivot.name = "BarPivot"
	pivot.position = Vector3(-BAR_W / 2.0, 0.0, 0.0)
	add_child(pivot)
	_bar = MeshInstance3D.new()
	var bar_mesh := BoxMesh.new()
	bar_mesh.size = Vector3(BAR_W, BAR_H, BAR_D)
	_bar.mesh = bar_mesh
	_bar.position = Vector3(BAR_W / 2.0, 0.0, 0.0)   # so scaling X keeps the left edge fixed
	_bar_mat = StandardMaterial3D.new()
	_bar_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_bar.material_override = _bar_mat
	pivot.add_child(_bar)

	_label = Label3D.new()
	_label.position = Vector3(0.0, BAR_H + 0.012, 0.0)
	_label.font_size = 36
	_label.pixel_size = 0.0007
	_label.modulate = Color(1, 1, 1)
	_label.outline_size = 6
	add_child(_label)

func _on_bus_event(name: String, payload: Dictionary) -> void:
	if int(payload.get("peer", -1)) != _local_id():
		return
	match name:
		"health:changed":
			_max = int(payload.get("max", _max))
			_hp = int(payload.get("hp", _hp))
			_redraw()
		"health:died":
			_hp = 0
			_redraw(true)
		"health:respawned":
			_max = int(payload.get("max", _max))
			_hp = int(payload.get("hp", _max))
			_redraw()

func _redraw(dead := false) -> void:
	if _bar == null:
		return
	var frac := 0.0 if _max <= 0 else clampf(float(_hp) / float(_max), 0.0, 1.0)
	# Scale the bar's X to the health fraction (left edge anchored by the pivot offset).
	_bar.get_parent().scale = Vector3(maxf(frac, 0.0001), 1.0, 1.0)
	# Green (full) -> red (empty).
	_bar_mat.albedo_color = Color(1.0 - frac, frac, 0.12)
	if _label:
		_label.text = "DOWN" if dead else "%d" % _hp
		_label.modulate = Color(1, 0.25, 0.25) if dead else Color(1, 1, 1)
