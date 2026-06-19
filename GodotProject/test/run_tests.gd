extends SceneTree
# Headless test runner. Run from the project dir:
#   Godot_v4.6.3-stable_win64_console.exe --headless --xr-mode off --path . -s res://test/run_tests.gd
# Exit code 0 = all green, 1 = failures. Add suites to SUITES below.
#
# `--xr-mode off` is REQUIRED when the Oculus/Quest OpenXR runtime is active on the
# PC: without it OpenXR init stalls the main loop before the first _process frame
# and the run hangs (timeout, no output). With XR off, the engine boots straight to
# normal mode and the suites run.
#
# Suites run on the first _process tick (NOT _initialize): nodes added to `root`
# during _initialize aren't fully in-tree yet, so get_tree()/group lookups return
# null. By the first frame the tree is live and add_child() is synchronously in-tree.

const SUITES: Array[String] = [
	"res://test/test_game_events.gd",
	"res://test/test_audio_haptics.gd",
	"res://test/test_interactables.gd",
	"res://test/test_platform.gd",
	"res://test/test_sequence.gd",
	"res://test/test_health.gd",
]

var _done := false

func _process(_delta: float) -> bool:
	if _done:
		return true
	_done = true
	var total := 0
	var failed := 0
	print("== HyperMage VR test run ==")
	for path in SUITES:
		var script = load(path)
		if script == null:
			print("  ERROR: cannot load suite ", path)
			failed += 1
			continue
		var suite = script.new()
		root.add_child(suite)
		for m in suite.get_method_list():
			var n: String = m.get("name", "")
			if not n.begins_with("test_"):
				continue
			suite.failures.clear()
			suite.checks = 0
			suite.call(n)
			total += 1
			if not suite.failures.is_empty():
				failed += 1
				for f in suite.failures:
					print("  FAIL  ", n, ": ", f)
			elif suite.checks == 0:
				# A test that ran no assertions almost certainly errored mid-method
				# (GDScript runtime errors abort silently) — treat as failure, not pass.
				failed += 1
				print("  FAIL  ", n, ": no checks ran (method errored or is empty)")
			else:
				print("  PASS  ", n, "  (", suite.checks, " checks)")
		suite.free()
	print("")
	print("Tests: ", total, "   Failed: ", failed)
	quit(1 if failed > 0 else 0)
	return true
