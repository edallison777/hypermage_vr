extends Node3D
# Equippable hitscan weapon (F7 — see GodotProject/FEATURE_PLAN.md). Group "weapon"
# (NOT "grabbable", so the trigger-based grab system ignores it). weapon_manager
# equips it (grip) and fires it (trigger); the fire RESOLUTION (raycast + damage) is
# server-authoritative in combat_manager. This node owns only the gun's own state:
# ammo + fire cooldown + the muzzle transform + the ammo readout.

@export var weapon_id: String = ""
@export var max_ammo: int = 12
@export var damage: int = 25
@export var fire_range: float = 50.0
@export var fire_cooldown: float = 0.25   # seconds between shots

var ammo: int = 0
var equipped_by: String = ""               # "" | "left" | "right"
var _cooldown := 0.0
var _ammo_lbl: Label3D = null

func _ready() -> void:
	add_to_group("weapon")
	ammo = max_ammo
	_ammo_lbl = get_node_or_null("AmmoLabel")
	_update_label()

func _process(delta: float) -> void:
	tick(delta)

# Cooldown countdown, split out so tests can drive it deterministically.
func tick(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown = maxf(0.0, _cooldown - delta)

func muzzle_transform() -> Transform3D:
	var m := get_node_or_null("Muzzle")
	return (m as Node3D).global_transform if m else global_transform

func can_fire() -> bool:
	return _cooldown <= 0.0 and ammo > 0

func is_empty() -> bool:
	return ammo <= 0

# Try to fire: consumes a round + starts the cooldown. Returns true if a shot went off.
func fire_consume() -> bool:
	if not can_fire():
		return false
	ammo -= 1
	_cooldown = fire_cooldown
	_update_label()
	return true

func reload() -> void:
	ammo = max_ammo
	_update_label()

func _update_label() -> void:
	if _ammo_lbl:
		_ammo_lbl.text = "%d/%d" % [ammo, max_ammo]
