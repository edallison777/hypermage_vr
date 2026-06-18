extends AnimatableBody3D
const Diag = preload("res://scripts/debug_flags.gd")
# A sliding "secret" wall slab driven by a lever/wheel Mechanism.
#
# Closed (mechanism value 0) it sits flush in the wall and blocks the passage,
# looking like ordinary masonry. As the linked mechanism's value goes 0 -> 1 the
# slab slides by `open_offset`, revealing the passage (and whatever is behind it).
#
# Linkage is by id: at startup it finds the Mechanism node named
# "Mechanism_<mechanism_id>" (they share the converter's id form) and listens to
# its `value_changed`. Because mechanism.gd emits value_changed on remote peers
# too (set_value_remote), the door opens the same amount on every client.
#
# An AnimatableBody3D moves its collider with it, so the player's CharacterBody3D
# is blocked while closed and can walk through once it has slid away.

@export var mechanism_id: String = ""
# Slab translation (in this node's parent space) at full open. Default: drop down.
@export var open_offset: Vector3 = Vector3(0, -2.4, 0)
# Travel speed as a fraction of full range per second (full open in ~1/SPEED s).
@export var speed: float = 1.5

var _closed_position: Vector3 = Vector3.ZERO
var _mech: Node = null
var _target: float = 0.0   # latest mechanism value (0..1)
var _cur: float = 0.0      # smoothed open amount the slab is actually at

func _ready() -> void:
	# We move the slab ourselves (kinematic teleport each physics frame) rather
	# than letting the physics server interpolate it.
	sync_to_physics = false
	_closed_position = position
	# Mechanisms join the "mechanism" group in their _ready; defer so they exist.
	call_deferred("_link")

func _link() -> void:
	var want := "Mechanism_" + mechanism_id
	for m in get_tree().get_nodes_in_group("mechanism"):
		if m.name == want:
			_mech = m
			if m.has_signal("value_changed") and not m.value_changed.is_connected(_on_value):
				m.value_changed.connect(_on_value)
			_target = m.value
			if Diag.ON:
				print("SecretDoor: ", name, " linked to ", m.name, " value=", m.value)
			return
	push_warning("SecretDoor '%s': mechanism '%s' not found" % [name, want])

func _on_value(v: float) -> void:
	_target = clampf(v, 0.0, 1.0)

func _physics_process(delta: float) -> void:
	if _cur == _target:
		return
	_cur = move_toward(_cur, _target, delta * speed)
	position = _closed_position + open_offset * _cur
