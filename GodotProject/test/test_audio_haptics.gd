extends "res://test/test_base.gd"
# Unit tests for the F1 audio + haptics primitives. Instantiates the manager scripts
# directly (not via the autoload globals) so the logic is exercised independently of
# project autoload registration, and without needing the WAVs to be imported (a
# synthesized in-code AudioStreamWAV stands in for a library entry).

const AudioMgr = preload("res://scripts/audio_manager.gd")
const HapticsMgr = preload("res://scripts/haptics.gd")

func _tiny_stream() -> AudioStreamWAV:
	var s := AudioStreamWAV.new()
	s.format = AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate = 22050
	s.data = PackedByteArray()
	s.data.resize(64)        # a few frames of silence
	return s

func test_play_3d_with_stream_spawns_player() -> void:
	var a = AudioMgr.new()
	add_child(a)
	var before := a.get_child_count()
	a.play_3d(_tiny_stream(), Vector3(1, 2, 3))
	check(a.get_child_count() > before, "play_3d spawned an AudioStreamPlayer3D")
	a.free()

func test_play_3d_missing_name_is_noop() -> void:
	var a = AudioMgr.new()
	add_child(a)
	var before := a.get_child_count()
	a.play_3d("nonexistent_sfx", Vector3.ZERO)
	check_eq(a.get_child_count(), before, "missing sfx name -> nothing spawned")
	a.free()

func test_play_3d_respects_concurrency_cap() -> void:
	var a = AudioMgr.new()
	add_child(a)
	var s := _tiny_stream()
	for i in range(a.MAX_CONCURRENT + 5):
		a.play_3d(s, Vector3.ZERO)
	check(a._active <= a.MAX_CONCURRENT, "active players capped at MAX_CONCURRENT")
	a.free()

func test_ambient_play_stop_no_crash() -> void:
	var a = AudioMgr.new()
	add_child(a)
	# No library loaded (WAVs may be unimported here) -> play_ambient no-ops cleanly;
	# inject a stream to exercise the player path.
	a._lib["ambient"] = _tiny_stream()
	a.play_ambient("ambient")
	a.stop_ambient()
	check(true, "ambient play/stop did not crash")
	a.free()

func test_ambient_imported_pcm_and_loops() -> void:
	# Guards the loop regression: ambient must import as PCM 16-bit (not QOA, or the
	# frame math is wrong and it clicks) and get a forward loop spanning the file.
	var a = AudioMgr.new()
	add_child(a)
	var s = a._lib.get("ambient")
	check(s != null, "ambient loaded into library")
	if s is AudioStreamWAV:
		check_eq(s.format, AudioStreamWAV.FORMAT_16_BITS, "ambient is PCM 16-bit (not QOA)")
		check_eq(s.loop_mode, AudioStreamWAV.LOOP_FORWARD, "ambient set to loop forward")
		check(s.loop_end == s.data.size() / 2 and s.loop_end > 0, "loop_end == frame count")
	a.free()

func test_haptics_noop_without_controllers() -> void:
	var h = HapticsMgr.new()
	add_child(h)
	h.pulse("both", 0.5, 0.05)        # no XRController3D in tree -> must not crash
	h.pulse("left")
	h.pulse_controller(null)
	check(true, "haptics no-op safely without controllers")
	h.free()
