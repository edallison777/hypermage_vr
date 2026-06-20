# Probe: confirm the exact property names the bake-ready converter mode must emit,
# so we don't silently drop properties. Run headless (ClassDB introspection only).
extends SceneTree

func _props(cls: String, needles: Array) -> Array[String]:
	var out: Array[String] = []
	for p in ClassDB.class_get_property_list(cls, false):
		var n: String = p.get("name", "")
		for needle in needles:
			if n.findn(needle) != -1 and not out.has(n):
				out.append(n)
	return out

func _process(_d: float) -> bool:
	var lines: Array[String] = []
	lines.append("BoxMesh uv2: %s"        % str(_props("BoxMesh", ["uv2"])))
	lines.append("Light3D bake: %s"       % str(_props("Light3D", ["bake"])))
	lines.append("GeometryInstance3D gi: %s" % str(_props("GeometryInstance3D", ["gi_"])))
	lines.append("LightmapGI props: %s"   % str(_props("LightmapGI", ["quality", "bounce", "environment", "directional", "texel", "interior", "max_texture", "bias", "denoise", "use_"])))
	var t := "\n".join(lines)
	print(t)
	var f := FileAccess.open("user://probe_bakeready.txt", FileAccess.WRITE)
	if f: f.store_string(t); f.close()
	quit()
	return true
