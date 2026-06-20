# Headless-bake feasibility probe (F9 step 1 de-risk).
# Reports the decisive facts about whether LightmapGI can bake without an editor window.
# Run: Godot_..._console.exe --headless --xr-mode off --path . -s res://tools/probe_bake.gd
# (writes findings to user://probe_bake.txt as well as stdout, since the console
#  process can zombie after quit() and drop buffered stdout — same trap as the test runner.)
extends SceneTree

func _process(_d: float) -> bool:
	var lines: Array[String] = []
	lines.append("=== headless bake probe ===")
	lines.append("godot version: %s" % Engine.get_version_info().get("string", "?"))

	# 1) Is there a RenderingDevice? The GPU lightmapper (LightmapperRD) needs one.
	#    The dummy --headless driver returns null here.
	var rd := RenderingServer.get_rendering_device()
	lines.append("RenderingServer.get_rendering_device(): %s" % ("PRESENT" if rd != null else "NULL"))
	if rd != null:
		lines.append("  rd device name: %s" % rd.get_device_name())

	# 2) Is LightmapGI.bake() reachable from script, and what is its arity?
	var lm := LightmapGI.new()
	lines.append("LightmapGI has_method('bake'): %s" % str(lm.has_method("bake")))
	for m in lm.get_method_list():
		if m.get("name", "") == "bake":
			lines.append("  bake() args: %s" % str(m.get("args", [])))
	# Lightmapper backend availability (ClassDB tells us if the RD lightmapper exists).
	lines.append("ClassDB has 'LightmapperRD': %s" % str(ClassDB.class_exists("LightmapperRD")))
	lm.free()

	# 3) Can we mesh-unwrap UV2 headlessly? (PlaneMesh -> ArrayMesh -> lightmap_unwrap)
	var pm := PlaneMesh.new()
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, pm.get_mesh_arrays())
	var uv_err := am.lightmap_unwrap(Transform3D.IDENTITY, 0.1)
	lines.append("ArrayMesh.lightmap_unwrap() -> %s (OK==%d)" % [str(uv_err), OK])

	var text := "\n".join(lines)
	print(text)
	var f := FileAccess.open("user://probe_bake.txt", FileAccess.WRITE)
	if f:
		f.store_string(text)
		f.close()
	quit()
	return true
