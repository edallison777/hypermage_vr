extends "res://test/test_base.gd"
# Unit tests for the torch-cone reveal geometry (hidden_writing.gd point_in_cone) — the
# pure distance + half-angle test. The per-frame torch query + fade are integration
# (flat harness / device).

const HiddenWriting = preload("res://scripts/hidden_writing.gd")

# Cone: origin at 0, pointing -Z, range 5, half-angle 14deg.
const ORIGIN := Vector3.ZERO
const DIR := Vector3(0, 0, -1)
const RANGE := 5.0
var _cos_half := cos(deg_to_rad(14.0))

func test_point_straight_ahead_in_range_is_lit() -> void:
	check(HiddenWriting.point_in_cone(Vector3(0, 0, -3), ORIGIN, DIR, RANGE, _cos_half),
			"a point straight down the cone within range is lit")

func test_point_behind_is_not_lit() -> void:
	check(not HiddenWriting.point_in_cone(Vector3(0, 0, 3), ORIGIN, DIR, RANGE, _cos_half),
			"a point behind the torch is not lit")

func test_point_beyond_range_is_not_lit() -> void:
	check(not HiddenWriting.point_in_cone(Vector3(0, 0, -8), ORIGIN, DIR, RANGE, _cos_half),
			"a point past the cone range is not lit")

func test_point_outside_angle_is_not_lit() -> void:
	# 3 m ahead but 2 m off-axis -> ~34deg, well outside the 14deg half-angle.
	check(not HiddenWriting.point_in_cone(Vector3(2, 0, -3), ORIGIN, DIR, RANGE, _cos_half),
			"a point outside the cone half-angle is not lit")

func test_point_just_inside_angle_is_lit() -> void:
	# 3 m ahead, 0.5 m off-axis -> ~9.5deg, inside 14deg.
	check(HiddenWriting.point_in_cone(Vector3(0.5, 0, -3), ORIGIN, DIR, RANGE, _cos_half),
			"a point just inside the cone half-angle is lit")
