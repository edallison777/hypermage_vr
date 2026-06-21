// Soft billboard puff for mist / waterfall spray particles. Compatibility renderer (Quest 3).
// Gives soft round particles WITHOUT a sprite texture: alpha falls off radially from the quad
// centre and is broken up by a little noise so puffs look like vapour, not discs. Billboarding
// is done in the vertex stage (ShaderMaterial has no billboard_mode flag). Reads the per-particle
// COLOR (CPUParticles sets rgb + a fade) so emitters can tint/fade over lifetime.
shader_type spatial;
render_mode blend_mix, cull_disabled, unshaded, shadows_disabled, depth_draw_never;

uniform vec3  tint : source_color = vec3(0.88, 0.92, 0.94);
uniform float softness = 1.0;     // edge feather (higher = softer)
uniform float density  = 0.85;    // overall opacity multiplier

float hash21(vec2 p){ p = fract(p * vec2(127.1, 311.7)); p += dot(p, p + 34.5); return fract(p.x * p.y); }
float vnoise(vec2 p){
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i), b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0)), d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void vertex(){
	// camera-facing billboard, keeping per-instance scale + world position
	mat4 mv = VIEW_MATRIX * MODEL_MATRIX;
	mv[0] = vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0);
	mv[1] = vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0);
	mv[2] = vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0);
	MODELVIEW_MATRIX = mv;
}

void fragment(){
	vec2 d = UV - vec2(0.5);
	float r = length(d) * 2.0;                         // 0 centre -> 1 edge
	float n = vnoise(UV * 4.0 + vec2(TIME * 0.05)) * 0.35 + 0.65;
	float a = smoothstep(1.0, 1.0 - clamp(softness, 0.05, 1.0), r) * n;
	ALBEDO = tint * COLOR.rgb;
	ALPHA  = clamp(a * COLOR.a * density, 0.0, 1.0);
}
