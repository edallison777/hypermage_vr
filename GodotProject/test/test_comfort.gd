extends "res://test/test_base.gd"
# F9 §4c.5 comfort — pure logic: settings cycle/persist/(de)serialise, the vignette
# intensity→alpha mapping, and the menu value formatting. The VR feel (teleport arc,
# snap turn, vignette look, menu poke) is device-verified; this guards the maths.

const ComfortScript = preload("res://scripts/comfort_settings.gd")
const VignetteScript = preload("res://scripts/comfort_vignette.gd")
const MenuScript = preload("res://scripts/comfort_menu.gd")

const TMP_CFG := "user://test_comfort.cfg"

func _fresh() -> Node:
	var c = ComfortScript.new()
	c._config_path = TMP_CFG
	return c

func test_defaults_are_comfort_first() -> void:
	var c = _fresh()
	check_eq(c.turn_mode, "snap", "snap turn on by default")
	check_eq(c.vignette_enabled, true, "vignette on by default")
	check_eq(c.locomotion_mode, "smooth", "smooth locomotion default")
	c.free()

func test_cycle_advances_and_wraps() -> void:
	var c = _fresh()
	check_eq(c.turn_mode, "snap", "start snap")
	check_eq(c.cycle("turn_mode"), "smooth", "cycle -> smooth")
	check_eq(c.cycle("turn_mode"), "snap", "cycle wraps -> snap")
	c.free()

func test_cycle_snap_degrees_sequence() -> void:
	var c = _fresh()
	c.snap_degrees = 15.0
	check_eq(c.cycle("snap_degrees"), 30.0, "15 -> 30")
	check_eq(c.cycle("snap_degrees"), 45.0, "30 -> 45")
	check_eq(c.cycle("snap_degrees"), 60.0, "45 -> 60")
	check_eq(c.cycle("snap_degrees"), 15.0, "60 wraps -> 15")
	c.free()

func test_cycle_unknown_key_noops() -> void:
	var c = _fresh()
	check_eq(c.cycle("nope"), null, "unknown key returns null")
	c.free()

func test_set_value_validates_key() -> void:
	var c = _fresh()
	c.set_value("not_a_setting", 5)
	check(not c.get("not_a_setting") is bool, "unknown key not created")
	c.set_value("turn_mode", "smooth")
	check_eq(c.turn_mode, "smooth", "known key set")
	c.free()

func test_save_load_roundtrip() -> void:
	var c = _fresh()
	c.snap_degrees = 30.0
	c.locomotion_mode = "teleport"
	c.vignette_strength = 0.3
	c.master_volume = 0.5
	c.save_settings()
	var c2 = _fresh()
	c2.load_settings()
	check_eq(c2.snap_degrees, 30.0, "snap persisted")
	check_eq(c2.locomotion_mode, "teleport", "loco persisted")
	check_eq(c2.vignette_strength, 0.3, "vignette persisted")
	check_eq(c2.master_volume, 0.5, "volume persisted")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TMP_CFG))
	c.free()
	c2.free()

func test_dict_roundtrip() -> void:
	var c = _fresh()
	c.seated_mode = true
	c.height_offset = 0.15
	var d = c.to_dict()
	var c2 = _fresh()
	c2.from_dict(d)
	check_eq(c2.seated_mode, true, "seated via dict")
	check_eq(c2.height_offset, 0.15, "height via dict")
	c.free()
	c2.free()

func test_snap_turn_radians() -> void:
	var c = _fresh()
	c.snap_degrees = 45.0
	check(abs(c.snap_turn_radians() - deg_to_rad(45.0)) < 0.0001, "45deg -> radians")
	c.free()

func test_move_hand_helper() -> void:
	var c = _fresh()
	check_eq(c.move_hand_is_left(), true, "left by default")
	c.locomotion_hand = "right"
	check_eq(c.move_hand_is_left(), false, "right after change")
	c.free()

func test_vignette_centre_clear_periphery_dark() -> void:
	# At full aperture the centre is clear and the far periphery is darkened.
	var centre = VignetteScript.compute_alpha_radius(0.0, 1.0, 0.6)
	var edge = VignetteScript.compute_alpha_radius(0.7, 1.0, 0.6)
	check(centre < 0.01, "centre clear")
	check(edge > centre, "edge darker than centre")

func test_vignette_zero_aperture_is_clear() -> void:
	var a = VignetteScript.compute_alpha_radius(0.7, 0.0, 0.6)
	check(a < 0.01, "no motion -> no vignette")

func test_vignette_strength_scales() -> void:
	var weak = VignetteScript.compute_alpha_radius(0.7, 1.0, 0.3)
	var strong = VignetteScript.compute_alpha_radius(0.7, 1.0, 0.9)
	check(strong > weak, "higher strength darkens more")

func test_menu_display_formats() -> void:
	check_eq(MenuScript._display("vignette_enabled", true), "ON", "bool true -> ON")
	check_eq(MenuScript._display("vignette_enabled", false), "OFF", "bool false -> OFF")
	check_eq(MenuScript._display("snap_degrees", 45.0), "45°", "degrees")
	check_eq(MenuScript._display("master_volume", 0.5), "50%", "percent")
	check_eq(MenuScript._display("locomotion_mode", "teleport"), "Teleport", "string capitalised")
	check_eq(MenuScript._display("height_offset", 0.15), "+0.15m", "height signed")
