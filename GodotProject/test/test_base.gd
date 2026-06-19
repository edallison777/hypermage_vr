extends Node
# Minimal assertion base for the headless test runner (test/run_tests.gd).
# A self-contained alternative to GUT: no addon, no network dependency, runs via
# `Godot --headless -s res://test/run_tests.gd`. Subclasses extend this by path
# (no class_name — unreliable headless) and define test_* methods.

var failures: Array[String] = []
var checks: int = 0

func check(cond: bool, msg: String) -> void:
	checks += 1
	if not cond:
		failures.append(msg)

func check_eq(got, want, msg: String) -> void:
	check(got == want, "%s -- got %s want %s" % [msg, str(got), str(want)])
