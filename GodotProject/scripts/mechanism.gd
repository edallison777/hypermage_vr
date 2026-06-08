extends Node3D
# A constrained interactable driven directly by the VR hand: a LEVER (swings about
# one local axis, clamped) or a WHEEL (rotates about its facing axis, accumulating).
# Lives inside a generated room; MechanismManager engages/drives it from a controller.
#
# Exposes a normalized `value` in [0, 1] and emits `value_changed(value)` — that is the
# hook a later step will use to change something in the environment per position.
#
# TEST VISIBILITY: the grab indicator (knob / rim marker) recolours red->green across
# travel with emission, and ValueLabel shows the live value, so motion is obvious.

signal value_changed(value: float)

@export_enum("lever", "wheel") var kind: String = "lever"
@export var axis: Vector3 = Vector3(1, 0, 0)        # local rotation axis
@export var min_angle: float = -0.785               # radians (lever limit / wheel min)
@export var max_angle: float = 0.785                # radians
@export var handle_local: Vector3 = Vector3(0, 0.5, 0)  # grip point in Pivot-local space

var value: float = 0.0

var _angle: float = 0.0
var _last_hand_ang: float = 0.0
var _pivot: Node3D = null
var _indicator: MeshInstance3D = null
var _label: Label3D = null
var _mat: StandardMaterial3D = null

func _ready() -> void:
	add_to_group("mechanism")
	_pivot = get_node_or_null("Pivot")
	_indicator = get_node_or_null("Pivot/Indicator")
	_label = get_node_or_null("ValueLabel")
	if _indicator:
		var m = _indicator.get_active_material(0)
		_mat = (m.duplicate() if m is StandardMaterial3D else StandardMaterial3D.new())
		_indicator.material_override = _mat
	# Rest at the low end so the full red->green range maps across the whole travel.
	_angle = min_angle
	_apply(false)
	print("Mechanism: ", name, " kind=", kind, " handle_world=", handle_global_position())

# World position of the grip point the hand must reach to engage. Follows the
# handle as the mechanism turns (the indicator sits here).
func handle_global_position() -> Vector3:
	if _pivot == null:
		return global_position
	return _pivot.to_global(handle_local)

func engage(hand_global: Vector3) -> void:
	if kind == "wheel":
		_last_hand_ang = _hand_angle(hand_global)

func release() -> void:
	pass

# Drive the mechanism from the hand's world position (called every frame while held).
func drive(hand_global: Vector3) -> void:
	var rel: Vector3 = to_local(hand_global)
	if kind == "lever":
		# swing about local X -> angle measured in the Y/Z plane
		_angle = clampf(atan2(rel.z, rel.y), min_angle, max_angle)
	else:
		# wheel: accumulate the change in hand angle about local Z
		var a := _hand_angle(hand_global)
		_angle = clampf(_angle + wrapf(a - _last_hand_ang, -PI, PI), min_angle, max_angle)
		_last_hand_ang = a
	_apply(true)

# Apply a value pushed from the network (other player turned it).
func set_value_remote(v: float) -> void:
	_angle = lerpf(min_angle, max_angle, clampf(v, 0.0, 1.0))
	_apply(false)

func _hand_angle(hand_global: Vector3) -> float:
	var rel: Vector3 = to_local(hand_global)
	return atan2(rel.y, rel.x)   # about local Z

func _apply(do_emit: bool) -> void:
	if _pivot:
		_pivot.transform.basis = Basis(axis.normalized(), _angle)
	var rng := max_angle - min_angle
	value = 0.0 if absf(rng) < 0.0001 else clampf((_angle - min_angle) / rng, 0.0, 1.0)
	var c := Color(1, 0, 0).lerp(Color(0, 1, 0), value)
	if _mat:
		_mat.albedo_color = c
		_mat.emission_enabled = true
		_mat.emission = c
		_mat.emission_energy_multiplier = 0.9
	if _label:
		_label.text = "%s %.2f" % [kind, value]
	if do_emit:
		value_changed.emit(value)
