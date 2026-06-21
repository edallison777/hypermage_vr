extends Node
## Overrides the imported glTF materials on every MeshInstance3D in this node's parent subtree
## with the unified watercolour surface shader, so instanced models (rocks, etc.) match the
## scene's watercolour style instead of showing their own photo-PBR. The converter attaches
## this (as a child node of the prop's StaticBody) when the scene style is "watercolour".
## The shader is triplanar/world-space, so it ignores the model's own UVs and just needs an
## albedo to wash — a shared rock albedo keeps every rock cohesive.

@export var albedo_path: String = "res://assets/textures/rock_face_03/rock_face_03_diff_1k.jpg"
@export var tiling: float = 0.3

func _ready() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/watercolour.gdshader")
	var tex := load(albedo_path)
	if tex != null:
		mat.set_shader_parameter("albedo_tex", tex)
	mat.set_shader_parameter("tiling", tiling)
	_apply(get_parent(), mat)

func _apply(n: Node, mat: Material) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		var count := 1
		if mi.mesh != null:
			count = max(mi.mesh.get_surface_count(), 1)
		for i in count:
			mi.set_surface_override_material(i, mat)
	for c in n.get_children():
		_apply(c, mat)
