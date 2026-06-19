extends "res://test/test_base.gd"
# Unit tests for F8 enemy health/death + the wave director's pure logic. The NavMesh
# chase + attack are integration (flat harness / device); here we drive take_damage and
# the wave/target maths directly.

const Enemy = preload("res://scripts/enemy.gd")
const EnemyManager = preload("res://scripts/enemy_manager.gd")

# Minimal stand-in for EnemyManager so a lethal hit has something to notify.
class MgrStub extends Node:
	var died: Node = null
	func on_enemy_died(e: Node) -> void:
		died = e

func _make_enemy(authority := true, max_hp := 30) -> Node:
	var e = Enemy.new()
	e.max_hp = max_hp
	e.set_authority(authority)
	add_child(e)              # _ready sets hp = max_hp, builds body + nav agent
	return e

func test_take_damage_reduces_hp() -> void:
	var e = _make_enemy(true, 30)
	e.take_damage(10)
	check_eq(e.hp, 20, "hp reduced by the damage")
	e.free()

func test_lethal_hit_kills_and_notifies() -> void:
	var e = _make_enemy(true, 30)
	var stub := MgrStub.new()
	e._mgr = stub
	e.take_damage(999)
	check_eq(e.hp, 0, "hp clamps at 0")
	check(stub.died == e, "manager is notified of the death")
	stub.free()
	e.free()

func test_puppet_ignores_damage() -> void:
	var e = _make_enemy(false, 30)   # not the authority -> a render puppet
	e.take_damage(10)
	check_eq(e.hp, 30, "a non-authority puppet does not mutate hp")
	e.free()

func test_wave_count_scales_with_difficulty() -> void:
	var m = EnemyManager.new()
	add_child(m)
	check_eq(m.wave_count(1), 3, "wave 1 = BASE_COUNT")
	check_eq(m.wave_count(2), 5, "wave 2 = +PER_WAVE")
	check_eq(m.wave_count(3), 7, "wave 3 = +2*PER_WAVE")
	m.free()

func test_nearest_player_target() -> void:
	var m = EnemyManager.new()
	add_child(m)
	var p := Node3D.new()
	p.add_to_group("player")
	add_child(p)
	p.global_position = Vector3(5, 0, 0)
	var tgt: Dictionary = m.nearest_player_target(Vector3.ZERO)
	check(not tgt.is_empty(), "a player in range is found")
	if not tgt.is_empty():
		check(tgt["pos"].is_equal_approx(Vector3(5, 0, 0)), "returns the player position")
	p.free()
	m.free()
