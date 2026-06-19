extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Server-authoritative combat resolution (F7 — see GodotProject/FEATURE_PLAN.md).
#
# Mirrors HealthManager/GameState: the SERVER (or, offline, this node as its own
# authority) is the only place a shot's outcome is decided. A client sends a FIRE
# intent (muzzle origin + direction + the weapon's damage); the authority raycasts
# its own physics world, and if the first thing hit is a destructible "target" it
# applies the damage and broadcasts the result on the F0 bus:
#   target:hit {id, hp, max}
#   target:destroyed {id}
# Target nodes (on every peer) react to those for VFX/removal; GameState can treat
# target:destroyed as an objective trigger. Player avatars don't exist on the server,
# so shots resolve against room geometry + targets only (co-op PvE).
#
# Lives at /root/HMVRGame/CombatManager. Target health is seeded from the room's
# "target" nodes by setup()/setup_offline() (after the room is loaded).

const EV_HIT       := "target:hit"
const EV_DESTROYED := "target:destroyed"

signal target_hit(id: String, hp: int)
signal target_destroyed(id: String)

var local_mode := false

var _hp: Dictionary = {}        # target_id -> hp
var _max: Dictionary = {}       # target_id -> max_hp
var _bus: Node = null

func _ready() -> void:
	add_to_group("combat")
	_bus = get_tree().get_first_node_in_group("game_events")

func setup() -> void:
	if multiplayer.is_server():
		_seed_targets()

func setup_offline() -> void:
	local_mode = true
	_seed_targets()

func _authority() -> bool:
	return local_mode or not multiplayer.has_multiplayer_peer() or multiplayer.is_server()

# Scan the room's target nodes and register their starting health.
func _seed_targets() -> void:
	_hp.clear()
	_max.clear()
	for t in get_tree().get_nodes_in_group("target"):
		register_target(str(t.target_id), int(t.max_hp))

func register_target(id: String, max_hp: int) -> void:
	if id == "":
		return
	_hp[id] = max_hp
	_max[id] = max_hp

func target_hp(id: String) -> int:
	return int(_hp.get(id, 0))

# ── Fire intent ─────────────────────────────────────────────────────────────────

# Called CLIENT-SIDE by weapon_manager on each shot. Routes to the authority.
func request_fire(origin: Vector3, dir: Vector3, damage: int) -> void:
	if _authority():
		_resolve_fire(origin, dir, damage)
	else:
		rpc_id(1, "_sv_fire", origin, dir, damage)

@rpc("any_peer", "reliable")
func _sv_fire(origin: Vector3, dir: Vector3, damage: int) -> void:
	if not multiplayer.is_server():
		return
	_resolve_fire(origin, dir, damage)

# Authority raycast. First solid thing hit wins; if it's a target, damage it (walls
# and props block the shot). The player's own body is excluded so a muzzle that sits
# just inside the capsule doesn't self-hit (offline only — the server has no body).
func _resolve_fire(origin: Vector3, dir: Vector3, damage: int) -> void:
	var world := get_viewport().world_3d
	if world == null:
		return
	var to := origin + dir.normalized() * 50.0
	var q := PhysicsRayQueryParameters3D.create(origin, to)
	q.collide_with_areas = false
	var excl: Array[RID] = []
	for p in get_tree().get_nodes_in_group("player"):
		if p is CollisionObject3D:
			excl.append(p.get_rid())
	q.exclude = excl
	var hit := world.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return
	var col = hit.get("collider")
	if col == null:
		return
	if col.is_in_group("target"):
		damage_target(str(col.target_id), damage)
	elif col.is_in_group("enemy"):
		col.take_damage(damage)        # F8: enemies take gunfire (authority-side)

# ── Authoritative mutation (pure: directly unit-tested) ────────────────────────────

func damage_target(id: String, amount: int) -> void:
	if not _hp.has(id) or int(_hp[id]) <= 0:
		return
	var hp := maxi(0, int(_hp[id]) - amount)
	_hp[id] = hp
	_emit(EV_HIT, {"id": id, "hp": hp, "max": int(_max.get(id, hp))})
	target_hit.emit(id, hp)
	if hp == 0:
		_emit(EV_DESTROYED, {"id": id})
		target_destroyed.emit(id)
		if Diag.ON:
			print("CombatManager: target ", id, " destroyed")

func _emit(name: String, payload: Dictionary) -> void:
	if _bus == null:
		_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.fire(name, payload)
