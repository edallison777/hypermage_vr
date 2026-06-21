extends OmniLight3D
# Torch flicker (F9) — varies an OmniLight's energy (and a touch of its range) organically so
# a "torch" reads as live fire rather than a steady bulb. Layered sines at incommensurate
# rates give a non-repeating flicker without per-frame randomness (cheap, MP-irrelevant —
# purely cosmetic and local). Attached by the converter `light` type when `flicker: true`.

@export var amount := 0.22       # depth of the dip (fraction of base energy)
@export var speed := 11.0        # flicker rate
@export var phase := 0.0         # per-light offset so torches don't pulse in unison

var _base_energy := 1.0
var _base_range := 1.0
var _t := 0.0

func _ready() -> void:
	_base_energy = light_energy
	_base_range = omni_range
	_t = phase

func _process(dt: float) -> void:
	_t += dt * speed
	# Three incommensurate sines -> organic, non-looping flicker in 0..1.
	var f: float = sin(_t) * 0.5 + sin(_t * 2.3 + 1.7) * 0.3 + sin(_t * 5.9 + 0.4) * 0.2
	var k: float = 1.0 - amount + amount * (f * 0.5 + 0.5)
	light_energy = _base_energy * k
	omni_range = _base_range * (0.97 + 0.03 * k)
