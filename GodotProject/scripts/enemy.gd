extends CharacterBody3D
const Diag = preload("res://scripts/debug_flags.gd")
# Enemy (F8 — see GodotProject/FEATURE_PLAN.md). Server-authoritative like the rest:
# on the authority (server, or offline = the local client) it runs its own AI —
# NavMesh-path chases the nearest player (NavigationAgent3D, with a direct-steer
# fallback when the nav map isn't ready), and when in range bites the player via the
# F5 HealthManager. It takes damage from F7 guns (combat_manager raycast → take_damage)
# and dies. EnemyManager spawns/owns them. (Networked puppet replication to remote
# clients rides with the full server multiplayer test; here the authority path is what
# offline play and device tests exercise.)
#
# On collision layer 1 so the combat raycast hits it; walls (mask bit 1) block it.

@export var max_hp: int = 30
@export var speed: float = 2.0
@export var damage: int = 10
@export var attack_range: float = 1.3
@export var attack_cooldown: float = 1.5

var enemy_id: String = ""
var authority: bool = false
var hp: int = 0

const GRAVITY := 12.0

const STUCK_LIMIT := 12.0       # despawn if no progress toward the player for this long

var _mgr: Node = null
var _health: Node = null
var _agent: NavigationAgent3D = null
var _atk_t := 0.0
var _mat: StandardMaterial3D = null
var _flash_t := 0.0
var _best_dist := INF           # closest planar distance to a player reached so far
var _stuck_t := 0.0             # time since that closest approach improved

func _ready() -> void:
	add_to_group("enemy")
	collision_layer = 1
	collision_mask = 1
	hp = max_hp
	_build_body()
	_agent = NavigationAgent3D.new()
	_agent.path_desired_distance = 0.4
	_agent.target_desired_distance = attack_range * 0.8
	add_child(_agent)
	_health = get_tree().get_first_node_in_group("health")

func _build_body() -> void:
	var col := CollisionShape3D.new()
	var caps := CapsuleShape3D.new()
	caps.radius = 0.3
	caps.height = 1.4
	col.shape = caps
	add_child(col)
	var mesh := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.3
	cm.height = 1.4
	mesh.mesh = cm
	_mat = StandardMaterial3D.new()
	_mat.albedo_color = Color(0.7, 0.2, 0.6)
	mesh.material_override = _mat
	add_child(mesh)

func set_authority(on: bool) -> void:
	authority = on

# Called on the authority by combat_manager when a shot connects.
func take_damage(amount: int) -> void:
	if not authority or hp <= 0:
		return
	hp = maxi(0, hp - amount)
	_flash_t = 0.1
	if hp == 0:
		if _mgr:
			_mgr.on_enemy_died(self)

func _process(delta: float) -> void:
	if _flash_t > 0.0:
		_flash_t -= delta
		if _mat:
			_mat.emission_enabled = _flash_t > 0.0
			_mat.emission = Color(1, 1, 1)

func _physics_process(delta: float) -> void:
	if not authority or _mgr == null:
		return
	var tgt: Dictionary = _mgr.nearest_player_target(global_position)
	if tgt.is_empty():
		return
	var tpos: Vector3 = tgt["pos"]
	var to_player := tpos - global_position
	to_player.y = 0.0
	var planar := to_player.length()

	# Stuck watchdog: if we never get closer to the player (wedged in geometry / outside
	# the navigable area), despawn so we don't keep the wave from ever clearing.
	if planar < _best_dist - 0.1:
		_best_dist = planar
		_stuck_t = 0.0
	else:
		_stuck_t += delta
		if _stuck_t >= STUCK_LIMIT and _mgr:
			_mgr.on_enemy_died(self)
			return

	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	else:
		velocity.y = 0.0

	if planar <= attack_range:
		velocity.x = 0.0
		velocity.z = 0.0
		move_and_slide()
		_atk_t -= delta
		if _atk_t <= 0.0:
			_atk_t = attack_cooldown
			_attack(int(tgt.get("peer", 1)))
		return

	var dir := to_player / planar          # direct fallback
	var nav_map := _agent.get_navigation_map()
	if nav_map.is_valid() and NavigationServer3D.map_get_iteration_id(nav_map) > 0:
		_agent.target_position = tpos
		var nd := _agent.get_next_path_position() - global_position
		nd.y = 0.0
		if nd.length() > 0.05:
			dir = nd.normalized()
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	move_and_slide()

func _attack(peer: int) -> void:
	if _health:
		_health.apply_damage(peer, damage, "enemy:" + enemy_id)
	Audio.play_3d("hurt", global_position, -2.0, 0.7)
	if Diag.ON:
		print("Enemy: ", enemy_id, " bit peer ", peer)
