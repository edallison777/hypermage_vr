// Falling waterfall sheet — a vertical plane/curved mesh of cascading water.
// Target: Godot Compatibility renderer (Quest 3 GL ES3). NO SCREEN_TEXTURE / DEPTH_TEXTURE
// (both unsupported in Compatibility), so depth-foam and screen refraction are faked with
// procedural streak-noise + fresnel. The look = long vertical foam streaks scrolling downward,
// bright white impact/base foam, a cool misty-dawn water tint, and a fresnel rim so it glows
// in the haze. All knobs are uniforms so the converter can tune it per scene.
shader_type spatial;
render_mode blend_mix, cull_disabled, shadows_disabled, specular_schlick_ggx, diffuse_lambert;

uniform vec3  water_color : source_color = vec3(0.50, 0.66, 0.70);
uniform vec3  foam_color  : source_color = vec3(0.93, 0.97, 0.98);
uniform float flow_speed     = 1.7;     // downward scroll (UV.v units / sec) — how fast it falls
uniform float streak_scale   = 7.0;     // across-fall streak count
uniform float streak_stretch = 16.0;    // along-fall stretch (long thin streaks)
uniform float foam_amount    = 0.55;    // 0..1 white-foam coverage
uniform float foam_emission  = 0.22;    // foam self-glow (reads through mist)
uniform float base_alpha     = 0.80;
uniform float fresnel_power  = 2.5;

// cheap value noise (no texture fetch)
float hash21(vec2 p){ p = fract(p * vec2(127.1, 311.7)); p += dot(p, p + 34.5); return fract(p.x * p.y); }
float vnoise(vec2 p){
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i), b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0)), d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
// two-octave stretched noise -> vertical streaks that scroll DOWN the sheet (device-verified:
// "+t" read as flowing UP on the QuadMesh, so we subtract t to push the foam streaks downward
// into the pool).
float streaks(vec2 uv, float t){
	vec2 p = vec2(uv.x * streak_scale, uv.y * streak_stretch - t);
	return vnoise(p) * 0.7 + vnoise(p * 2.3 + 11.0) * 0.3;
}

void fragment(){
	float t = TIME * flow_speed;
	float s1 = streaks(UV, t);
	float s2 = streaks(UV * vec2(1.6, 1.2) + vec2(0.37, 0.0), t * 1.35);
	float flow = mix(s1, s2, 0.5);

	// more foam at the lip (UV.y~0, impact) and the base (UV.y~1, plunge)
	float ends = smoothstep(0.80, 1.0, UV.y) + smoothstep(0.20, 0.0, UV.y);
	float foam = smoothstep(1.0 - foam_amount, 1.0, flow + ends * 0.5);

	// 3-tap procedural normal so the streaks catch the sun
	float e = 0.0035;
	float gx = streaks(UV + vec2(e, 0.0), t) - flow;
	float gy = streaks(UV + vec2(0.0, e), t) - flow;
	NORMAL_MAP = normalize(vec3(-gx, -gy, 0.25) * vec3(3.0, 3.0, 1.0)) * 0.5 + 0.5;

	float fres = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), fresnel_power);

	// break the hard rectangular quad: feather the two vertical edges (wavering with the flow
	// so the sheet has a living, irregular outline) and taper the very top where it spills.
	float edge_wave = (vnoise(vec2(UV.y * 9.0 + t, 0.0)) - 0.5) * 0.06;
	float edges = smoothstep(0.0, 0.10, UV.x + edge_wave) * smoothstep(1.0, 0.90, UV.x + edge_wave);
	float top   = smoothstep(0.0, 0.06, UV.y);
	float shape = edges * top;

	ALBEDO    = mix(water_color, foam_color, foam);
	ROUGHNESS = mix(0.16, 0.55, foam);    // glassy water, rougher foam
	METALLIC  = 0.0;
	ALPHA     = clamp((base_alpha + foam * 0.2 + fres * 0.15) * shape, 0.0, 1.0);
	EMISSION  = foam_color * foam * foam_emission;
}
