extends Node
const Diag = preload("res://scripts/debug_flags.gd")
# Server-authoritative player health (F5 — see GodotProject/FEATURE_PLAN.md).
#
# Lives at /root/HMVRGame/HealthManager in BOTH the client (main_vr.tscn) and the
# dedicated server (server_main.tscn), so RPCs route by the matching node path —
# the same pattern PlayerSync / RoomManager use.
#
# AUTHORITY MODEL (locked cross-cutting decision): health is server-authoritative.
# The server is the only place HP is decided. A client never mutates HP directly:
# its hazards detect that ITS OWN player body took damage and send an INTENT —
#   client  request_damage(amount, source)  -> rpc_id(1, _sv_request)
#   server  validates (alive? per-source cooldown) -> apply_damage()             }
#   server  broadcasts the RESULT on the GameEvents bus (fire -> _deliver to all) } authority
# Every client then learns the new HP / death / respawn from the bus event, so the
# HUD and feedback derive from a single source of truth and stay consistent. The
# discrete health events flow through the same bus as buttons/sequences (F0), as the
# plan intends ("damage dealt" is a discrete event); the validation that makes them
# authoritative lives here rather than in the generic bus relay.
#
# OFFLINE (local room / flat harness): no server peer, so this node is its own
# authority — request_damage applies locally and the bus emits locally (local_mode).

const MAX_HP          := 100
const RESPAWN_DELAY   := 3.0      # seconds dead before auto-respawn at full HP
const REQUEST_COOLDOWN := 0.20    # min seconds between accepted hits per (peer, source)

# Discrete bus event names broadcast to every peer (authoritative results).
const EV_CHANGED   := "health:changed"     # {peer, hp, max}
const EV_DIED      := "health:died"        # {peer, source}
const EV_RESPAWNED := "health:respawned"   # {peer, hp, max}

# Local mirror signals (for in-process listeners / tests that prefer signals to the bus).
signal health_changed(peer: int, hp: int, max_hp: int)
signal died(peer: int, source: String)
signal respawned(peer: int)

# Offline single-player: act as our own authority and emit locally.
var local_mode := false

var _hp: Dictionary = {}        # peer_id -> int
var _dead: Dictionary = {}      # peer_id -> bool
var _last_req: Dictionary = {}  # "peer:source" -> seconds (server-side anti-spam)
var _bus: Node = null

func _ready() -> void:
	add_to_group("health")
	_bus = get_tree().get_first_node_in_group("game_events")

# Called by server_main._ready() (server only) once the ENet peer is live, mirroring
# PlayerSync/RoomManager. Registers each peer at full HP on connect.
func setup() -> void:
	if not multiplayer.is_server():
		return
	multiplayer.peer_connected.connect(_sv_peer_up)
	multiplayer.peer_disconnected.connect(_sv_peer_down)

# Called by the offline path (vr_main / flat harness) to register the lone local
# player and make this node self-authoritative.
func setup_offline() -> void:
	local_mode = true
	register(local_id())

func local_id() -> int:
	return multiplayer.get_unique_id() if multiplayer.has_multiplayer_peer() else 1

# ── Queries (every peer; HP for non-local peers is only meaningful on the authority) ─

func get_hp(peer: int) -> int:
	return int(_hp.get(peer, MAX_HP))

func is_dead(peer: int) -> bool:
	return bool(_dead.get(peer, false))

func max_hp() -> int:
	return MAX_HP

# ── Server peer lifecycle ────────────────────────────────────────────────────────

func _sv_peer_up(id: int) -> void:
	register(id)

func _sv_peer_down(id: int) -> void:
	_hp.erase(id)
	_dead.erase(id)

# ── Intent: a client reports its own player taking damage ──────────────────────────

# Called CLIENT-SIDE by a hazard when the local player body is in it. Routes the
# intent to the authority; the result comes back over the bus.
func request_damage(amount: float, source: String) -> void:
	if local_mode or not multiplayer.has_multiplayer_peer():
		_authoritative_request(local_id(), amount, source)
	elif multiplayer.is_server():
		_authoritative_request(local_id(), amount, source)
	else:
		rpc_id(1, "_sv_request", amount, source)

@rpc("any_peer", "reliable")
func _sv_request(amount: float, source: String) -> void:
	if not multiplayer.is_server():
		return
	_authoritative_request(multiplayer.get_remote_sender_id(), amount, source)

# Runs on the authority only. Gates the request (alive + per-source cooldown), then
# applies it. Cooldown lives here (not in apply_damage) so apply_damage stays a pure,
# directly-testable mutation.
func _authoritative_request(peer: int, amount: float, source: String) -> void:
	if is_dead(peer):
		return
	var key := "%d:%s" % [peer, source]
	var now := Time.get_ticks_msec() / 1000.0
	if now - float(_last_req.get(key, -999.0)) < REQUEST_COOLDOWN:
		return
	_last_req[key] = now
	apply_damage(peer, amount, source)

# ── Authoritative mutations (pure: no networking, no timing — directly unit-tested) ─

func register(peer: int) -> void:
	_hp[peer] = MAX_HP
	_dead[peer] = false
	_emit_changed(peer)

# Reduce HP. Clamps at 0; the 0-crossing fires death exactly once and schedules a
# respawn. Returns the resulting HP.
func apply_damage(peer: int, amount: float, source: String) -> int:
	if is_dead(peer):
		return 0
	var hp := clampi(get_hp(peer) - int(round(amount)), 0, MAX_HP)
	_hp[peer] = hp
	_emit_changed(peer)
	if hp == 0:
		_dead[peer] = true
		_emit(EV_DIED, {"peer": peer, "source": source})
		died.emit(peer, source)
		if Diag.ON:
			print("HealthManager: peer ", peer, " died from ", source)
		if is_inside_tree():
			get_tree().create_timer(RESPAWN_DELAY).timeout.connect(revive.bind(peer))
	return hp

func heal(peer: int, amount: float) -> int:
	if is_dead(peer):
		return 0
	var hp := clampi(get_hp(peer) + int(round(amount)), 0, MAX_HP)
	_hp[peer] = hp
	_emit_changed(peer)
	return hp

# Back to full HP and alive again; broadcasts respawn so the owning client can
# reposition its rig to a spawn point.
func revive(peer: int) -> void:
	_hp[peer] = MAX_HP
	_dead[peer] = false
	_emit(EV_RESPAWNED, {"peer": peer, "hp": MAX_HP, "max": MAX_HP})
	_emit_changed(peer)
	respawned.emit(peer)

# ── Broadcast helpers ──────────────────────────────────────────────────────────────

func _emit_changed(peer: int) -> void:
	_emit(EV_CHANGED, {"peer": peer, "hp": get_hp(peer), "max": MAX_HP})
	health_changed.emit(peer, get_hp(peer), MAX_HP)

# Send a result to every peer. On the authority this goes through the bus's server
# relay (fire -> _ingest -> _deliver to all, server-sequenced); offline it emits
# locally. Either way every listener sees it exactly once, in order.
func _emit(name: String, payload: Dictionary) -> void:
	if _bus == null:
		_bus = get_tree().get_first_node_in_group("game_events")
	if _bus:
		_bus.fire(name, payload)
