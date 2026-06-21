extends MeshInstance3D
# Comfort vignette (F9 §4c.5) — a peripheral tunnelling overlay that darkens the edges of
# vision while the player moves or turns, the standard VR nausea-reliever. Parent this under
# the XRCamera3D; it builds its own quad + radial shader. Locomotion calls set_motion(0..1)
# each frame with the current movement/turn intensity; the darkening eases in/out smoothly
# and is scaled by Comfort.vignette_strength (0 disables it).
#
# Pure: the intensity→aperture mapping is testable headless (compute_alpha_radius); the
# look is device-verified.

const EASE_IN  := 8.0    # how fast the tunnel closes when motion starts
const EASE_OUT := 4.0    # how fast it opens when motion stops (slower = gentler)

var _target := 0.0       # desired intensity this frame (set by locomotion)
var _current := 0.0      # smoothed intensity actually applied
var _mat: ShaderMaterial = null

const SHADER := """
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, depth_test_disabled, shadows_disabled, fog_disabled;
uniform float aperture : hint_range(0.0, 1.0) = 0.0;  // 0 = fully open (clear), 1 = max tunnel
uniform float max_strength : hint_range(0.0, 1.0) = 0.6;
void fragment() {
	float r = length(UV - vec2(0.5));        // 0 centre .. ~0.707 corner
	// Clear radius shrinks as aperture grows; periphery fades to black.
	float inner = mix(0.75, 0.18, aperture);
	float outer = mix(0.95, 0.42, aperture);
	float a = smoothstep(inner, outer, r) * max_strength * aperture;
	ALBEDO = vec3(0.0);
	ALPHA = a;
}
"""

func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(2.2, 2.2)   # generous so the edges always cover the FOV periphery
	mesh = quad
	position = Vector3(0.0, 0.0, -0.35)   # just in front of the eyes
	cast_shadow = SHADOW_CASTING_SETTING_OFF
	var sh := Shader.new()
	sh.code = SHADER
	_mat = ShaderMaterial.new()
	_mat.shader = sh
	material_override = _mat
	_apply()
	set_process(true)

func set_motion(intensity: float) -> void:
	_target = clampf(intensity, 0.0, 1.0)

func _process(dt: float) -> void:
	var rate := EASE_IN if _target > _current else EASE_OUT
	_current = move_toward(_current, _target, rate * dt)
	_apply()

func _apply() -> void:
	if _mat == null:
		return
	var c = _comfort()
	var enabled: bool = c.vignette_enabled if c else true
	var strength: float = (c.vignette_strength if c else 0.6) if enabled else 0.0
	visible = strength > 0.0 and _current > 0.001
	_mat.set_shader_parameter("aperture", _current)
	_mat.set_shader_parameter("max_strength", strength)

func _comfort():
	# Resolve the Comfort autoload if present (absent under some headless test paths).
	return get_node_or_null("/root/Comfort")

# Pure mapping exposed for tests: the alpha at a given radius for a given intensity+strength.
static func compute_alpha_radius(r: float, aperture: float, strength: float) -> float:
	var inner: float = lerpf(0.75, 0.18, aperture)
	var outer: float = lerpf(0.95, 0.42, aperture)
	return smoothstep(inner, outer, r) * strength * aperture
