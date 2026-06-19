extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Enemy spawner / wave director (F8 — see GodotProject/FEATURE_PLAN.md). Lives at
# /root/HMVRGame/EnemyManager in both scenes. Server-authoritative like the other
# managers; offline it's its own authority. It spawns escalating WAVES of enemies at
# the room's "enemy_spawn" markers, advances to the next wave once the field is clear,
# and broadcasts discrete events on the F0 bus: "wave:started" {wave, count},
# "enemy:spawned" {id}, "enemy:died" {id}. It also answers enemies' nearest_player_target()
# queries. (Networked puppet replication to remote clients is part of the full server
# multiplayer test; offline the spawned enemies are the real, authoritative ones.)

const Enemy = preload("res://scripts/enemy.gd")

const BASE_COUNT  := 3       # enemies in wave 1
const PER_WAVE    := 2       # extra enemies per subsequent wave (difficulty)
const WAVE_DELAY  := 5.0     # seconds between clearing a wave and the next
const FIRST_DELAY := 3.0     # grace before wave 1

var local_mode := false

var _wave := 0
var _alive: Dictionary = {}        # id -> enemy
var _next_id := 0
var _spawns: Array[Vector3] = []
var _between := false
var _timer := 0.0
var _started := false
var _bus: Node = null
var _health: Node = null

func _ready() -> void:
	add_to_group("enemy_manager")
	_bus = get_tree().get_first_node_in_group("game_events")
	_health = get_tree().get_first_node_in_group("health")

func setup() -> void:
	if multiplayer.is_server():
		_begin()

func setup_offline() -> void:
	local_mode = true
	_begin()

func _authority() -> bool:
	return local_mode or not multiplayer.has_multiplayer_peer() or multiplayer.is_server()

func _begin() -> void:
	_spawns.clear()
	for m in get_tree().get_nodes_in_group("enemy_spawn"):
		_spawns.append((m as Node3D).global_position)
	_wave = 0
	_alive.clear()
	_between = true
	_timer = FIRST_DELAY
	_started = true
	if Diag.ON:
		print("EnemyManager: begin, spawn points=", _spawns.size())

# ── Queries ────────────────────────────────────────────────────────────────────────

func wave() -> int:
	return _wave

func alive_count() -> int:
	return _alive.size()

# Nearest player to `from`, as {peer, pos}. Offline that's the local player body
# (group "player"); the networked server variant (PlayerSync positions) rides with the
# server multiplayer test.
func nearest_player_target(from: Vector3) -> Dictionary:
	var best := {}
	var best_d := INF
	for b in get_tree().get_nodes_in_group("player"):
		var d: float = from.distance_to((b as Node3D).global_position)
		if d < best_d:
			best_d = d
			best = {"peer": _local_peer(), "pos": (b as Node3D).global_position}
	return best

func _local_peer() -> int:
	return _health.local_id() if _health else 1

# ── Wave loop (authority) ──────────────────────────────────────────────────────────

func _process(delta: float) -> void:
	if not _started or not _authority():
		return
	if _between:
		_timer -= delta
		if _timer <= 0.0:
			_between = false
			_start_wave()
	elif _alive.is_empty():
		_between = true
		_timer = WAVE_DELAY

func _start_wave() -> void:
	_wave += 1
	var count := BASE_COUNT + (_wave - 1) * PER_WAVE
	for i in count:
		_spawn_one()
	if _bus:
		_bus.fire("wave:started", {"wave": _wave, "count": count})
	if Diag.ON:
		print("EnemyManager: wave ", _wave, " -> ", count, " enemies")

func wave_count(wave_num: int) -> int:
	return BASE_COUNT + maxi(0, wave_num - 1) * PER_WAVE

func _spawn_one() -> void:
	if _spawns.is_empty():
		return
	var e = Enemy.new()
	e.enemy_id = str(_next_id)
	_next_id += 1
	e.set_authority(true)
	e._mgr = self
	# Harder waves -> tougher/faster enemies (difficulty).
	e.max_hp = 30 + (_wave - 1) * 10
	e.speed = 2.0 + minf(_wave - 1, 4) * 0.25
	get_parent().add_child(e)
	e.global_position = _spawns[randi() % _spawns.size()] + Vector3(0, 0.9, 0)
	_alive[e.enemy_id] = e
	if _bus:
		_bus.fire("enemy:spawned", {"id": e.enemy_id})

func on_enemy_died(e: Node) -> void:
	if not _alive.has(e.enemy_id):
		return
	_alive.erase(e.enemy_id)
	Audio.play_3d("success", (e as Node3D).global_position, -4.0, 1.2)
	if _bus:
		_bus.fire("enemy:died", {"id": e.enemy_id})
	e.queue_free()
