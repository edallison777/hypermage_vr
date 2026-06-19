extends "res://test/test_base.gd"
# Unit tests for the F7 weapon ammo / fire-gating logic (weapon.gd) — the pure parts
# (ammo, cooldown, reload). The equip/fire input + raycast are exercised in the flat
# harness / on device.

const Weapon = preload("res://scripts/weapon.gd")

func _make(ammo := 3, cd := 0.0) -> Node:
	var w = Weapon.new()
	w.max_ammo = ammo
	w.fire_cooldown = cd
	add_child(w)            # _ready sets ammo = max_ammo
	return w

func test_fire_consumes_ammo() -> void:
	var w = _make(3, 0.0)
	check(w.fire_consume(), "first shot fires")
	check_eq(w.ammo, 2, "ammo decremented")
	w.free()

func test_cannot_fire_when_empty() -> void:
	var w = _make(1, 0.0)
	check(w.fire_consume(), "fires the last round")
	check(w.is_empty(), "now empty")
	check(not w.fire_consume(), "cannot fire when empty")
	check_eq(w.ammo, 0, "ammo stays at 0")
	w.free()

func test_cooldown_gates_fire() -> void:
	var w = _make(5, 0.5)
	check(w.fire_consume(), "first shot fires")
	check(not w.can_fire(), "cooling down -> cannot fire yet")
	w.tick(0.5)
	check(w.can_fire(), "fire allowed again after cooldown elapses")
	w.free()

func test_reload_restores_ammo() -> void:
	var w = _make(3, 0.0)
	w.fire_consume(); w.fire_consume()
	check_eq(w.ammo, 1, "two shots spent")
	w.reload()
	check_eq(w.ammo, 3, "reload restores to max")
	w.free()
