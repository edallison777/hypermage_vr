extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Base reactor (F0 — see GodotProject/FEATURE_PLAN.md).
#
# Listens for one discrete bus event (by name) and runs a reaction. Generalises the
# link-by-id pattern in secret_door.gd (which stays value-driven; not migrated here).
# Because events are server-sequenced by the bus, every reactor reacts identically
# on every peer. Subclasses override _react(payload); or connect to `triggered`.

signal triggered(payload: Dictionary)

@export var trigger_event: String = ""

var _bus: Node = null

func _ready() -> void:
	# The bus is an autoload (/root/GameEvents), so it always exists before any
	# reactor's _ready. Connect our OWN method (not a lambda) so the connection is
	# auto-dropped if this reactor frees — no dangling calls into a freed object.
	_bus = get_tree().get_first_node_in_group("game_events")
	if _bus == null:
		push_warning("Reactor '%s': no GameEvents bus found" % name)
		return
	if trigger_event == "":
		push_warning("Reactor '%s': trigger_event is empty" % name)
		return
	_bus.event.connect(_on_bus_event)

func _on_bus_event(event_name: String, payload: Dictionary) -> void:
	if event_name != trigger_event:
		return
	if Diag.ON:
		print("Reactor: ", name, " triggered by '", trigger_event, "'")
	triggered.emit(payload)
	_react(payload)

# Override in subclasses to do something when the trigger event fires.
func _react(_payload: Dictionary) -> void:
	pass
