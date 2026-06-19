extends "res://scripts/interactable.gd"
const Diag = preload("res://scripts/debug_flags.gd")
# Damaging volume (F5): an Area3D that hurts the LOCAL player while their body is in
# it. Detection runs client-side (each client watches its own player body, group
# "player"); damage itself is decided by the authority — the hazard only sends an
# INTENT via HealthManager.request_damage(), which the server validates and broadcasts
# (see health_manager.gd). So the hazard never touches HP directly.
#
# Modes:
#   instant=false (default): damage-over-time — `damage_per_second` applied every
#     `interval` seconds while the player stands in it (lava/gas/spikes field).
#   instant=true: one hit on entry (a spike strike / trap trigger).
#
# Only the local player is reported: on each peer the only body in group "player" is
# that peer's own locomotion capsule, so every client reports just its own damage.

@export var damage_per_second: float = 20.0
@export var interval: float = 0.5
@export var instant: bool = false

var _area: Area3D = null
var _health: Node = null
var _inside := false
var _accum := 0.0

func _ready() -> void:
	super._ready()
	add_to_group("hazard")
	_area = get_node_or_null("Area")
	if _area:
		_area.body_entered.connect(_on_enter)
		_area.body_exited.connect(_on_exit)

func _on_enter(b: Node) -> void:
	if not b.is_in_group("player"):
		return
	_inside = true
	_accum = 0.0
	if instant:
		_hit(damage_per_second)            # one fixed bite on entry

func _on_exit(b: Node) -> void:
	if b.is_in_group("player"):
		_inside = false

func _process(delta: float) -> void:
	if instant or not _inside:
		return
	_accum += delta
	if _accum >= interval:
		_accum -= interval
		_hit(damage_per_second * interval)

func _hit(amount: float) -> void:
	if _health == null:
		_health = get_tree().get_first_node_in_group("health")
	if _health == null:
		return
	_health.request_damage(amount, interactable_id)
	# Local feedback (predicted; the authoritative HP comes back over the bus).
	Audio.play_3d("hurt", global_position, -2.0, 1.0)
	Haptics.pulse("both", 0.6, 0.10)
	if Diag.ON:
		print("Hazard: ", interactable_id, " hit for ", amount)
