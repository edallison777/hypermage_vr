extends AnimatableBody3D
const Diag = preload("res://scripts/debug_flags.gd")
# Rising/lowering platform (F3 — see GodotProject/FEATURE_PLAN.md).
#
# A moving floor the player RIDES. The deck is an AnimatableBody3D on the WALKABLE
# layer (bit 1 = block + bit 3 = walkable), so locomotion's downward floor-probe
# (_follow_floor) detects the deck and raises/lowers the rig with it — the player is
# carried with no extra code. Vertical travel only (the floor-probe is vertical).
#
# Position is a normalized value 0..1 -> position = start + travel * value, eased at
# `speed`. The value is set one of three ways (`mode`):
#   "mechanism" : tracks a Mechanism's value_changed (like secret_door) — id linkage.
#   "toggle"    : a bus event (button/switch) flips it to the far endpoint.
#   "auto"      : oscillates 0..1 forever on `auto_period` (good for a ride demo).
# mechanism/toggle are network-consistent (their driver replicates); auto runs per
# client and may drift over time — fine offline / single-rider.

const WALKABLE_LAYER := 1 | (1 << 2)     # = 5, must match locomotion WALKABLE_MASK

@export_enum("auto", "toggle", "mechanism") var mode: String = "auto"
@export var travel: Vector3 = Vector3(0.0, 2.5, 0.0)   # displacement at value = 1
@export var speed: float = 0.4                          # value units/sec (toggle/mechanism)
@export var auto_period: float = 8.0                    # seconds for a full up+down (auto)
@export var mechanism_id: String = ""                   # mode "mechanism"
@export var trigger_event: String = "interact:button"   # mode "toggle"
@export var source_id: String = ""                      # mode "toggle" id filter

var _start: Vector3
var _target := 0.0
var _cur := 0.0
var _t := 0.0
var _bus: Node = null
var _moving := false
var _rumble_cd := 0.0

func _ready() -> void:
	sync_to_physics = false                  # we teleport it each physics frame
	collision_layer = WALKABLE_LAYER
	_start = position
	_bus = get_tree().get_first_node_in_group("game_events")
	if mode == "toggle" and _bus:
		_bus.event.connect(_on_bus)
	elif mode == "mechanism":
		call_deferred("_link_mechanism")     # mechanisms join their group in _ready

func _link_mechanism() -> void:
	var want := "Mechanism_" + mechanism_id
	for m in get_tree().get_nodes_in_group("mechanism"):
		if m.name == want and m.has_signal("value_changed"):
			m.value_changed.connect(func(v: float) -> void: _target = clampf(v, 0.0, 1.0))
			_target = m.value
			return
	push_warning("MovingPlatform '%s': mechanism '%s' not found" % [name, want])

func _on_bus(event_name: String, payload: Dictionary) -> void:
	if event_name != trigger_event:
		return
	if source_id != "" and str(payload.get("id", "")) != source_id:
		return
	_target = 1.0 - _target                  # flip commanded endpoint (reverses even mid-travel)

func _physics_process(dt: float) -> void:
	_rumble_cd = maxf(0.0, _rumble_cd - dt)
	var prev := _cur
	if mode == "auto":
		_t += dt
		_cur = 0.5 - 0.5 * cos(TAU * _t / maxf(0.5, auto_period))
	else:
		if is_equal_approx(_cur, _target):
			_set_moving(false)
			return
		_cur = move_toward(_cur, _target, speed * dt)
	position = _start + travel * _cur
	_set_moving(absf(_cur - prev) > 0.0001)

func _set_moving(m: bool) -> void:
	if m and not _moving and _rumble_cd <= 0.0:
		_rumble_cd = 1.0
		Audio.play_3d("door_rumble", global_position, -4.0)
	_moving = m
