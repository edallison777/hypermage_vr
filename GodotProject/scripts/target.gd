extends StaticBody3D
# Destructible target (F7 — see GodotProject/FEATURE_PLAN.md). A StaticBody3D so the
# combat_manager raycast hits it directly (hit.collider is this node, group "target",
# carrying target_id). It owns NO health — the authority (combat_manager) decides hits
# and broadcasts target:hit / target:destroyed; every peer's target node just reacts:
# a brief flash on hit, hide + collision-off on destroy. GameState can use
# target:destroyed (match_id = target_id) as an objective trigger.

@export var target_id: String = ""
@export var max_hp: int = 50

var _bus: Node = null
var _mesh: MeshInstance3D = null
var _shape: CollisionShape3D = null
var _flash_t := 0.0
var _mat: StandardMaterial3D = null
var _base_emission := Color(0, 0, 0)

func _ready() -> void:
	add_to_group("target")
	_mesh = get_node_or_null("Mesh")
	_shape = get_node_or_null("Collision")
	if _mesh and _mesh.get_surface_override_material(0) is StandardMaterial3D:
		_mat = _mesh.get_surface_override_material(0)
		_base_emission = _mat.emission if _mat.emission_enabled else Color(0, 0, 0)
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.event.connect(_on_event)

func _on_event(name: String, payload: Dictionary) -> void:
	if str(payload.get("id", "")) != target_id:
		return
	if name == "target:hit":
		_flash()
	elif name == "target:destroyed":
		_destroy()

func _flash() -> void:
	Audio.play_3d("hurt", global_position, -4.0, 1.4)
	if _mat:
		_mat.emission_enabled = true
		_mat.emission = Color(1, 1, 1)
		_flash_t = 0.10

func _process(delta: float) -> void:
	if _flash_t > 0.0:
		_flash_t -= delta
		if _flash_t <= 0.0 and _mat:
			_mat.emission = _base_emission
			_mat.emission_enabled = _base_emission != Color(0, 0, 0)

func _destroy() -> void:
	Audio.play_3d("success", global_position, -2.0, 0.7)
	visible = false
	if _shape:
		_shape.disabled = true
	collision_layer = 0
