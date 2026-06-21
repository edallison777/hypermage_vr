// Unified WATERCOLOUR surface style for the rural scene (rock, cliff, ground). Compatibility
// renderer (Quest 3 GL ES3). Deliberately FLATTENS photo detail into soft pigment washes so
// simple geometry stops reading as "photo wrapped on a box". The look:
//   - albedo triplanar-sampled, heavily desaturated and pulled toward a cohesive pale palette
//   - soft flat shading (no specular, no normal map) — gentle tonal washes, not crisp PBR
//   - procedural PAPER GRAIN multiplied in (pigment soaking into paper)
//   - pigment DARKENING at the silhouette (watercolour's wet edges / granulation)
//   - a faint hand-painted WOBBLE so straight box edges waver
// All uniforms are per-material so the converter can give each surface its own wash.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_back, world_vertex_coords;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap;
uniform float tiling          = 0.3;    // albedo world tiles/m
uniform vec3  wash_tint : source_color = vec3(0.82, 0.84, 0.80);
uniform float wash_amount     = 0.22;   // gentle pull toward the palette (keep surface hue)
uniform float desaturate      = 0.35;   // soften colour but DON'T bleach to grey
uniform float lighten         = 0.06;   // slight paper lift
uniform float edge_pigment    = 0.5;    // darker silhouette = form definition
uniform float paper_strength  = 0.55;
uniform float paper_scale     = 16.0;
uniform float wobble          = 0.025;

float hash21(vec2 p){ p = fract(p * vec2(127.1, 311.7)); p += dot(p, p + 34.5); return fract(p.x * p.y); }
float vnoise(vec2 p){
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i), b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0)), d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

varying vec3 v_wpos;
varying vec3 v_wnorm;

void vertex(){
	// world_vertex_coords: VERTEX/NORMAL are already world-space here
	v_wpos  = VERTEX;
	v_wnorm = normalize(NORMAL);
}

vec3 tri_albedo(vec3 wp, vec3 n){
	vec3 bn = abs(n); bn /= max(bn.x + bn.y + bn.z, 0.001);
	vec3 cx = texture(albedo_tex, wp.zy * tiling).rgb;
	vec3 cy = texture(albedo_tex, wp.xz * tiling).rgb;
	vec3 cz = texture(albedo_tex, wp.xy * tiling).rgb;
	return cx * bn.x + cy * bn.y + cz * bn.z;
}

void fragment(){
	// hand-painted waver: nudge the sample position with low-freq noise
	float w = (vnoise(v_wpos.xz * 2.5) - 0.5) * wobble;
	vec3 wp = v_wpos + vec3(w, 0.0, w);

	vec3 base = tri_albedo(wp, v_wnorm);
	// desaturate, then pull toward the cohesive wash palette
	float lum = dot(base, vec3(0.299, 0.587, 0.114));
	base = mix(base, vec3(lum), desaturate);
	base = mix(base, wash_tint, wash_amount);
	base += lighten;

	// paper grain: two octaves, world-space, multiplied (pigment in the paper tooth)
	float paper = vnoise(wp.xz * paper_scale) * 0.5 + vnoise(wp.xz * paper_scale * 2.7 + 9.0) * 0.5;
	base *= mix(1.0, 0.82 + paper * 0.36, paper_strength);

	// pigment pooling at the silhouette — darken at grazing view angles
	float fres = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 2.0);
	base *= mix(1.0, 1.0 - edge_pigment, fres);

	ALBEDO    = clamp(base, 0.0, 1.0);
	ROUGHNESS = 1.0;
	METALLIC  = 0.0;
}
