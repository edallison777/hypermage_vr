// Horizontal water surface — plunge pool and river. Compatibility renderer (Quest 3 GL ES3),
// so NO depth/screen texture: "depth" colour and shore foam are faked with fresnel + procedural
// noise. The look = animated ripple normals catching the sun as sparkles, a fresnel blend from
// deep water colour (head-on) to the misty sky tint (grazing), optional downstream flow for the
// river, and drifting foam. Knobs are uniforms for per-scene tuning by the converter.
shader_type spatial;
render_mode blend_mix, cull_back, shadows_disabled, specular_schlick_ggx, diffuse_lambert;

uniform vec3  deep_color    : source_color = vec3(0.09, 0.20, 0.24);
uniform vec3  shallow_color : source_color = vec3(0.34, 0.52, 0.55);
uniform vec3  sky_tint      : source_color = vec3(0.74, 0.80, 0.84); // misty-dawn sky for fresnel
uniform vec3  foam_color    : source_color = vec3(0.90, 0.95, 0.96);
uniform float ripple_scale     = 3.2;     // ripple tiling across the surface
uniform float ripple_speed     = 0.30;    // ripple animation rate
uniform float normal_strength  = 0.40;    // ripple bumpiness
uniform vec2  flow_dir         = vec2(0.0, 0.0); // (0,0)=still pool; e.g. (0,1)=river downstream
uniform float flow_speed       = 0.18;
uniform float fresnel_power    = 4.0;
uniform float foam_amount      = 0.10;    // drifting surface foam (raise for turbulent water)
uniform float foam_emission    = 0.10;
uniform float surface_alpha    = 0.90;
uniform float sparkle          = 0.6;     // sun-glint sharpness

float hash21(vec2 p){ p = fract(p * vec2(127.1, 311.7)); p += dot(p, p + 34.5); return fract(p.x * p.y); }
float vnoise(vec2 p){
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i), b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0)), d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
// two crossing animated noise layers -> lively ripples
float ripple(vec2 uv, float t){
	return vnoise(uv + vec2(t * 0.6, t * 0.2)) * 0.6
	     + vnoise(uv * 1.9 - vec2(t * 0.3, t * 0.5)) * 0.4;
}

void fragment(){
	float t = TIME * ripple_speed;
	vec2 fuv = UV * ripple_scale - flow_dir * (TIME * flow_speed);

	float r  = ripple(fuv, t);
	float e  = 0.01;
	float gx = ripple(fuv + vec2(e, 0.0), t) - r;
	float gy = ripple(fuv + vec2(0.0, e), t) - r;
	NORMAL_MAP = normalize(vec3(-gx, -gy, 1.0 / max(normal_strength, 0.001))) * 0.5 + 0.5;

	float fres = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), fresnel_power);

	// drifting foam patches
	float foam = smoothstep(1.0 - foam_amount, 1.0, ripple(fuv * 0.7, t * 1.3));

	vec3 col = mix(deep_color, shallow_color, clamp(r * 0.5 + 0.5, 0.0, 1.0));
	col = mix(col, sky_tint, fres * 0.65);

	// foamy waterline: a band of foam hugging the irregular shore so the pool doesn't end on a
	// hard rectangular line. edge = 0 centre -> 1 at the plane border, wobbled by noise.
	float edge = max(abs(UV.x - 0.5), abs(UV.y - 0.5)) * 2.0;
	edge += (vnoise(UV * 6.0 + vec2(t * 0.1)) - 0.5) * 0.16;
	float shore_foam = smoothstep(0.72, 0.92, edge);
	col = mix(col, foam_color, max(foam, shore_foam));
	float rim = 1.0 - smoothstep(0.90, 1.0, edge);   // fade the very edge to nothing

	ALBEDO    = col;
	ROUGHNESS = mix(0.04, 0.5, max(foam, shore_foam));   // glossy water, rough foam
	METALLIC  = 0.0;
	ALPHA     = clamp((mix(surface_alpha, 1.0, fres) + foam * 0.1) * rim, 0.0, 1.0);
	EMISSION  = foam_color * max(foam, shore_foam) * foam_emission;
	SPECULAR  = sparkle;
}
