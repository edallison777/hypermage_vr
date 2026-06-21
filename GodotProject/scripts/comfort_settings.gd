extends Node
# Autoload "Comfort" (F9 §4c.5) — player comfort & accessibility settings, persisted to
# user://comfort.cfg. Read by locomotion (turn mode / teleport / handedness / height),
# the comfort vignette, the world-space settings menu, and audio. Emits `changed` whenever
# a value changes so live nodes re-read.
#
# Comfort-first DEFAULTS: snap-turn + vignette ON out of the box (smooth turn is the single
# biggest nausea source in VR). Everything is overridable from the in-headset menu.
#
# Pure logic (cycle/mappings/(de)serialise) is headless-testable; `_config_path` is
# overridable so tests don't touch the real user config.

signal changed

const CONFIG_PATH := "user://comfort.cfg"

# Allowed values per key, in cycle order — drives both the menu buttons and validation.
const OPTIONS := {
	"locomotion_mode":   ["smooth", "teleport"],
	"turn_mode":         ["snap", "smooth"],
	"snap_degrees":      [15.0, 30.0, 45.0, 60.0],
	"locomotion_hand":   ["left", "right"],
	"vignette_enabled":  [true, false],
	"vignette_strength": [0.0, 0.3, 0.6, 1.0],
	"seated_mode":       [false, true],
	"captions_enabled":  [false, true],
	"master_volume":     [0.0, 0.25, 0.5, 0.75, 1.0],
	"height_offset":     [-0.30, -0.15, 0.0, 0.15, 0.30],
}

# Live values (defaults = comfort-first).
var locomotion_mode := "smooth"
var turn_mode := "snap"
var snap_degrees := 45.0
var locomotion_hand := "left"
var vignette_enabled := true
var vignette_strength := 0.6
var seated_mode := false
var captions_enabled := false
var master_volume := 1.0
var height_offset := 0.0

var _config_path := CONFIG_PATH

func _ready() -> void:
	load_settings()
	apply_audio()

# ── serialise ────────────────────────────────────────────────────────────────
func to_dict() -> Dictionary:
	return {
		"locomotion_mode": locomotion_mode, "turn_mode": turn_mode,
		"snap_degrees": snap_degrees, "locomotion_hand": locomotion_hand,
		"vignette_enabled": vignette_enabled, "vignette_strength": vignette_strength,
		"seated_mode": seated_mode, "captions_enabled": captions_enabled,
		"master_volume": master_volume, "height_offset": height_offset,
	}

func from_dict(d: Dictionary) -> void:
	for k in to_dict().keys():
		if d.has(k):
			set(k, d[k])

func save_settings() -> void:
	var cf := ConfigFile.new()
	for k in to_dict().keys():
		cf.set_value("comfort", k, get(k))
	cf.save(_config_path)

func load_settings() -> void:
	var cf := ConfigFile.new()
	if cf.load(_config_path) != OK:
		return   # first run — keep defaults
	for k in to_dict().keys():
		if cf.has_section_key("comfort", k):
			set(k, cf.get_value("comfort", k))

# ── mutate ───────────────────────────────────────────────────────────────────
func set_value(key: String, value) -> void:
	if not OPTIONS.has(key):
		return
	if get(key) == value:
		return
	set(key, value)
	_after_change(key)

func cycle(key: String) -> Variant:
	# Advance a key to the next value in its OPTIONS list (wraps). The menu pokes this.
	if not OPTIONS.has(key):
		return null
	var opts: Array = OPTIONS[key]
	var i := opts.find(get(key))
	var nv = opts[(i + 1) % opts.size()] if i >= 0 else opts[0]
	set(key, nv)
	_after_change(key)
	return nv

func _after_change(key: String) -> void:
	if key == "master_volume":
		apply_audio()
	save_settings()
	changed.emit()

# ── helpers ──────────────────────────────────────────────────────────────────
func snap_turn_radians() -> float:
	return deg_to_rad(snap_degrees)

func move_hand_is_left() -> bool:
	return locomotion_hand == "left"

func apply_audio() -> void:
	# Map 0..1 to the Master bus dB (linear_to_db(0) = -inf -> mute).
	var bus := AudioServer.get_bus_index("Master")
	if bus < 0:
		return
	if master_volume <= 0.0:
		AudioServer.set_bus_mute(bus, true)
	else:
		AudioServer.set_bus_mute(bus, false)
		AudioServer.set_bus_volume_db(bus, linear_to_db(master_volume))
