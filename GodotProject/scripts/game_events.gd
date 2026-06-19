extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Network-consistent DISCRETE event bus (F0 — see GodotProject/FEATURE_PLAN.md).
#
# This is the single relay choke point for one-shot gameplay events — button
# pressed, sequence advanced, +score, took damage, enemy died, etc. — as opposed
# to CONTINUOUS state (held-object transform, mechanism value) which the existing
# managers stream at 20 Hz with last-writer-wins. Discrete events must fire EXACTLY
# ONCE on every peer in the SAME ORDER, so they are server-sequenced:
#
#   client  fire()  -> rpc_id(1, _ingest)            (to the server)
#   server  _ingest -> rpc(_deliver) to ALL peers     (incl. the original sender)
#   every peer + server then emits `event` locally, once, in the server's order.
#
# Registered as the autoload "GameEvents" (project.godot), so it lives at the
# stable path /root/GameEvents on every peer (RPC matches by path) and exists
# before any room loads. Consumers DO NOT reference the autoload global; they find
# it via the "game_events" group, so the same code works under the headless test
# runner (which instantiates the bus by hand).
#
# Offline (no multiplayer peer, or `local_mode` set for the offline local room):
# fire() emits locally and immediately, skipping the RPC path.

signal event(name: String, payload: Dictionary)

# Set true by the offline local-room path (no server peer) so fire() emits locally
# even though multiplayer.is_server() is true-by-default with no peer.
var local_mode: bool = false

func _ready() -> void:
	add_to_group("game_events")
	if Diag.ON:
		print("GameEvents: ready, local_mode=", local_mode)

# Fire a discrete, network-consistent event. `name` is a free-form string
# (convention: "domain:verb", e.g. "interact:activate", "score:add").
func fire(name: String, payload: Dictionary = {}) -> void:
	if local_mode or not multiplayer.has_multiplayer_peer():
		event.emit(name, payload)
		return
	if multiplayer.is_server():
		_ingest(name, payload)          # server originates: sequence it directly
	else:
		rpc_id(1, "_ingest", name, payload)

# Convenience subscriber: invoke `callable(payload)` only for events whose name
# matches `name`. (No unsubscribe in F0 — reactors live for the scene lifetime.)
func on(name: String, callable: Callable) -> void:
	event.connect(func(n: String, p: Dictionary) -> void:
		if n == name:
			callable.call(p))

# ── Server relay ────────────────────────────────────────────────────────────────

# Runs only on the server (clients target id 1; the server calls it directly).
@rpc("any_peer", "reliable")
func _ingest(name: String, payload: Dictionary) -> void:
	if not multiplayer.is_server():
		return
	rpc("_deliver", name, payload)      # call_local -> also delivers on the server

# Broadcast from the server (authority) to every peer, including the sender, and
# locally on the server. This is the one place `event` is emitted in networked play.
@rpc("authority", "call_local", "reliable")
func _deliver(name: String, payload: Dictionary) -> void:
	if Diag.ON:
		print("GameEvents: deliver ", name, " ", payload)
	event.emit(name, payload)
