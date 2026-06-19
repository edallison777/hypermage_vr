extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Audio primitive (F1 — see GodotProject/FEATURE_PLAN.md). Autoload "Audio".
#
# Two channels:
#  - play_3d(name, world_pos): a transient AudioStreamPlayer3D one-shot at a world
#    position (positional SFX: grab, throw, lever tick, door thud). Frees itself when
#    done; capped so a burst can't spawn unbounded players.
#  - play_ambient(name)/stop_ambient(): a single looping, non-positional bed.
#
# SFX are placeholder WAVs from tools/gen_placeholder_sfx.py; drop files with the
# same names from the Phase-8 pipeline to upgrade. Safe everywhere: if a stream is
# missing (e.g. assets not imported) calls no-op.

const SFX_DIR := "res://assets/audio/sfx/"
const SFX_NAMES := ["ui_click", "grab", "throw", "lever_tick", "door_rumble", "ambient"]
const LOOPING := ["ambient"]            # streams that loop forever when played
const MAX_CONCURRENT := 24
# The looping streams are imported as PCM (compress/mode=0) so data.size() is the true
# 16-bit frame count and loop_end below is exact. (With QOA compression data.size()
# isn't frames, so the loop cuts mid-buffer and clicks once per wrap — and import-time
# loop_mode didn't reliably take, so the loop is set here in code instead.)

var _lib: Dictionary = {}               # name -> AudioStream
var _ambient: AudioStreamPlayer = null
var _active := 0

func _ready() -> void:
	for n in SFX_NAMES:
		var s = load(SFX_DIR + n + ".wav")
		if s == null:
			push_warning("Audio: missing SFX '%s'" % n)
			continue
		if n in LOOPING and s is AudioStreamWAV:
			s.loop_mode = AudioStreamWAV.LOOP_FORWARD
			s.loop_begin = 0
			s.loop_end = s.data.size() / 2      # PCM 16-bit mono -> 2 bytes/frame
		_lib[n] = s
	if Diag.ON:
		print("Audio: loaded ", _lib.size(), " sfx; ambient loop_end=",
			(_lib["ambient"].loop_end if _lib.has("ambient") else -1))

# One-shot positional SFX at a world position. `name` is a library key OR an
# AudioStream. Non-looping streams only (looping ones never free).
func play_3d(name, world_pos: Vector3, volume_db := 0.0, pitch := 1.0) -> void:
	var stream: AudioStream = name if name is AudioStream else _lib.get(name)
	if stream == null or _active >= MAX_CONCURRENT:
		return
	var p := AudioStreamPlayer3D.new()
	p.stream = stream
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.unit_size = 4.0
	p.max_distance = 25.0
	add_child(p)                            # parent is a plain Node -> position is world
	p.global_position = world_pos
	_active += 1
	p.finished.connect(func() -> void:
		_active -= 1
		p.queue_free())
	p.play()

# Looping, non-positional ambient bed (one at a time).
func play_ambient(name := "ambient", volume_db := -8.0) -> void:
	var stream: AudioStream = _lib.get(name)
	if stream == null:
		return
	if _ambient == null:
		_ambient = AudioStreamPlayer.new()
		add_child(_ambient)
	_ambient.stream = stream
	_ambient.volume_db = volume_db
	if not _ambient.playing:
		_ambient.play()

func stop_ambient() -> void:
	if _ambient and _ambient.playing:
		_ambient.stop()
