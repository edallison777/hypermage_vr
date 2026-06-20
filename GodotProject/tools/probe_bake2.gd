# Probe 2: can we get a RenderingDevice with an offscreen driver, and does
# LightmapGI expose bake() anywhere in ClassDB? Decides if any automated GPU bake exists.
# Run WITHOUT --headless, forcing: --display-driver headless --rendering-driver vulkan --xr-mode off
extends SceneTree

func _process(_d: float) -> bool:
	var lines: Array[String] = []
	lines.append("=== probe2 ===")
	lines.append("video adapter: %s" % RenderingServer.get_video_adapter_name())
	var rd := RenderingServer.get_rendering_device()
	lines.append("get_rendering_device(): %s" % ("PRESENT" if rd != null else "NULL"))
	if rd != null:
		lines.append("  rd device: %s" % rd.get_device_name())
	# All ClassDB methods of LightmapGI mentioning bake:
	var found := false
	for m in ClassDB.class_get_method_list("LightmapGI", true):
		var n: String = m.get("name", "")
		if n.findn("bake") != -1:
			lines.append("  LightmapGI method: %s" % n)
			found = true
	if not found:
		lines.append("  LightmapGI: NO method name contains 'bake'")
	var text := "\n".join(lines)
	print(text)
	var f := FileAccess.open("user://probe_bake2.txt", FileAccess.WRITE)
	if f: f.store_string(text); f.close()
	quit()
	return true
