# HyperMage VR (Godot) — Feature Development Plan

Status: DRAFT (2026-06-19). Owner: Ed. Engine: Godot 4.6.3, Quest 3, ENet multiplayer
over ECS Fargate. Levels are generated from ScenePlan JSON by
`tools/sceneplan_to_tscn.py` and must stay agent-authorable.

This plan covers the **addition and testing** of gameplay features on top of the
working base (VR rendering, grab/throw, lever/wheel mechanisms, secret door,
doorways, staircases, multiplayer, agent-generated rooms).

---

## 1. Cross-cutting decisions (locked before building)

These are cheap to decide now and expensive to retrofit. **Treat as binding for
all phases below.**

1. **Authority model.** Health, damage, scoring, enemy state, and projectile hit
   resolution are **server-authoritative**. Clients send *intent* and predict
   *visuals* only; the server decides outcomes and broadcasts them. Co-op puzzle
   events (buttons, sequences, doors) may stay client-origin + server-relay (the
   existing pattern) since there's no adversary — but they flow through the same
   bus so they can be promoted to authoritative later without touching callers.

2. **Quest 3 performance budget.** Target **90 fps**, mobile/gl_compatibility
   renderer. Soft ceilings to profile against from F5 onward: draw calls, active
   RigidBodies, simultaneous projectiles, enemy count, dynamic lights. "Realistic
   graphics" (F9) spends from this budget last, once scene contents are known.

3. **Everything stays converter-generated.** Each new object/behaviour must be
   expressible in a ScenePlan and emitted by `sceneplan_to_tscn.py`. No
   hand-built-in-editor content. New node types get a converter emitter + a
   script + (where useful) a test JSON.

4. **Testing strategy.** The build→reboot→sideload loop is ~10 min, so logic must
   be testable **off the headset**:
   - **Parse-check** every changed script (already in use).
   - **GUT unit tests** (`test/`) for pure logic: sequence state machine, damage
     math, scoring, bus ordering. Run headless in CI-style.
   - **Desktop flat-mode harness**: run `main_vr` without XR, free-fly camera +
     keyboard to fire interactions, so puzzle/score/health logic is exercised on
     a PC in seconds.
   - **Headset** reserved for what genuinely needs VR: haptics, spatial audio,
     ergonomics, aim. Reboot the Quest after each APK build (doze wedges
     controllers — see `godot-controller-oracle`).
   - **Multiplayer**: headless PC client + Quest (the established 2-client test).

---

## 2. Networking model — two distinct channels

Conflating these is the main design trap. Both are already present in the code;
F0 formalises the second.

- **Continuous state** (held-object transform @20 Hz, mechanism value @20 Hz):
  unreliable, last-writer-wins, sender → server rebroadcast → peers apply. Already
  solved per-manager (`grab_manager.sync_held/do_throw`, `mechanism_manager.sync_value`).
  Leave as-is; optionally factor a helper later.
- **Discrete events** (button pressed, sequence advanced, door open, damage dealt,
  +score, enemy spawned/died): reliable, ordered, fire **exactly once on every
  peer in the same order**. This is what sequences, scoring, health, and enemies
  all need and what's missing today. **F0 builds this** (the event bus).

---

## 3. Phase plan

Each phase: dependency-ordered, with how it's tested. F-numbering avoids clashing
with the existing G-phases.

Status: ✅ done · 🔨 in progress · ⬜ not started. (Commit hashes for completed phases.)

| Phase | Feature | Depends on | Status |
|---|---|---|---|
| **F0** | Event bus + base `Interactable`/`Reactor` contracts; test runner + flat-mode harness | — | ✅ `fe6efe9` |
| **F1** | Sound (spatial 3D + ambient) and haptics primitives | F0 | ✅ `b2a5055` |
| **F2** | Simple interactables: buttons, pressure plates, toggle switches, proximity volumes | F0 | ✅ `d44b170` |
| **F3** | Rising/lowering platforms | F0, F2 | ✅ `3fe628f` |
| **F4** | Sequence puzzle (ordered interaction, resets on wrong order) | F0, F2 | ✅ `8e6e4e4` |
| **F5** | Health/damage model (server-authoritative) + death/respawn + HUD | F0, F1 | ✅ this commit |
| **F6** | Point scoring + objectives + win/lose + DynamoDB persistence/leaderboard | F0, F5 | ⬜ |
| **F7** | Guns: projectiles/beams, VFX, holster, ammo pickups | F0, F1, F5 | ⬜ |
| **F8** | Enemies: NavMesh, take/inflict damage, spawn waves, difficulty | F0, F5, F7 | ⬜ |
| **F9** | Realistic graphics pass + comfort/accessibility (teleport, vignette, settings) | all | ⬜ |

Known follow-up (not yet scheduled): **throwing physics/feel** needs improving — flagged
during F2 device testing; address standalone or within F7.

### Rationale for the order
- **F0 first** — the bus is the spine every later feature reuses; building it now,
  while only 3 interactables exist, is the cheapest it will ever be.
- **F1 before mechanics** — audio/haptics are reused everywhere and are cheap,
  low-risk polish-per-hour; ties into the existing Phase-8 audio pipeline.
- **F5 before F7/F8** — health/damage is the shared dependency of guns and enemies;
  both are meaningless without it.
- **F9 last** — on Quest's tile GPU, art is a perf minefield with low early
  gameplay payoff. Keep materials/lighting clean throughout; spend real art effort
  once mechanics are stable and the scene's contents are known.

### Additional functionality folded into the phases
- HUD (wrist/world-space) — F5.
- VFX (muzzle flash, beam trails, impact, destruction) — F7.
- Pickups/consumables, inventory/holster — F7.
- NavMesh, wave/difficulty — F8.
- Comfort (teleport option, vignette), settings, handedness — F9.
- Leaderboards via existing DynamoDB reward persistence (72h TTL) — F6.
- Checkpoints / puzzle-state save — F4/F6.

---

## 4. F0 — Interaction framework + test harness (BUILT ✅ 2026-06-19)

**Goal:** a single network-consistent discrete-event bus, a base contract every
interactable/reactor conforms to, and the off-headset test tooling — without
disturbing the working grab/mechanism/secret-door systems.

**Status: implemented and unit-tested green (5/5). Device regression pending.**
Files added: `scripts/game_events.gd`, `scripts/interactable.gd`,
`scripts/reactor.gd`, `scripts/reactors/light_reactor.gd`, `scripts/flat_harness.gd`,
`scenes/flat_test.tscn`, `test/{run_tests,test_base,test_game_events}.gd`.
Edited: `project.godot` (autoload), `scripts/vr_main.gd` (offline `local_mode`).

**Run the tests:**
`Godot_v4.6.3-stable_win64_console.exe --headless --xr-mode off --path . -s res://test/run_tests.gd`
(`--xr-mode off` is required when the Oculus runtime is live, else OpenXR init hangs
the run.) **Run the flat harness on the PC:**
`Godot_v4.6.3-stable_win64.exe --path . res://scenes/flat_test.tscn`.

### 4.1 The event bus — `scripts/game_events.gd`
**Refinement vs original sketch:** implemented as the **autoload `GameEvents`**
(`/root/GameEvents`) rather than a node duplicated into both scenes. It has no scene
dependencies, the path is identical on every peer (so RPC matches), it exists before
any room loads, and it avoids editing both `.tscn` files. Consumers never reference
the autoload global — they find it via the `"game_events"` group, so the same code
works under the headless runner (which instantiates the bus by hand). `local_mode`
is set from `vr_main`'s offline path via group lookup; networked play leaves it false
and the no-peer case auto-emits locally anyway.

API:
```gdscript
signal event(name: String, payload: Dictionary)   # everyone connects here

func fire(name, payload := {}) -> void   # network-consistent discrete event
func on(name, callable) -> void          # convenience: connect + filter by name
```

Relay (single choke point — replaces per-system copy/paste):
- `fire()` on a client → `rpc_id(1, _ingest, name, payload)` (reliable).
- Server `_ingest` → `rpc(_deliver, name, payload)` to **all** peers (incl. the
  original sender) → each peer (and the server) emits `event` locally.
- Server-sequenced delivery guarantees identical **ordering** on every peer
  (critical for sequence puzzles and scoring). Sender pays one round-trip; worth it.
- `local_mode` (offline / no peer): `fire()` emits `event` locally immediately.

A later **server-authoritative** path (`request()` → server validates → `_deliver`)
slots in beside `_ingest` for F5/F6 without changing callers.

### 4.2 Base contracts
- `scripts/interactable.gd` — `interactable_id`, joins group `"interactable"`,
  exposes `handle_global_position()` for proximity, and `fire_event(verb, extra)`
  which fires `interact:<verb>` on the bus with the id folded into the payload.
  **Deferred:** wiring the existing lever/wheel to also fire discrete bus events on
  threshold crossings is left to the first real consumer (F2/F4) so F0 stays strictly
  additive — `mechanism.gd`/`secret_door.gd` are untouched in F0.
- `scripts/reactor.gd` — finds the bus via group, connects its OWN method to
  `event` and filters by `trigger_event` (connecting a method, not a lambda, so the
  connection auto-drops when the reactor frees — no dangling calls). Subclasses
  override `_react(payload)` or listen to the `triggered` signal. Generalises the
  link-by-id pattern in `secret_door.gd` (which stays value-driven; not forced here).
  `scripts/reactors/light_reactor.gd` is the proof subclass (toggles a Light3D).

### 4.3 Test tooling (built — GUT NOT used)
- **Custom headless runner** instead of GUT: `test/run_tests.gd` (a `SceneTree`
  script) + `test/test_base.gd` (assert helpers) + `test/test_game_events.gd`.
  Chose this over vendoring GUT to avoid the network dependency and the addon/
  `class_name` headless pitfalls this project has hit. Suites extend the base by
  path and define `test_*` methods; the runner executes them on the first `_process`
  tick (nodes added during `_initialize` aren't fully in-tree yet).
- Tests use the single autoload bus (so interactables/reactors, which look it up by
  group, share the exact bus the test observes) and clean up their own connections.
- **Flat-mode harness** — `scenes/flat_test.tscn` + `scripts/flat_harness.gd`: loads
  a generated room **without** the XR rig, free-fly camera (WASD/QE + RMB-look), and
  `T` fires `test:toggle_light` → a `LightReactor` toggles a lamp. The PC proof of
  the bus→reactor path; extend per feature (e.g. a key to `activate()` the nearest
  interactable for F4).

### 4.4 Proof of F0 (definition of done)
1. ✅ Test suite green headless (5/5: offline emit, `on()` filter, reactor match,
   interactable scoped event, interactive-scripts compile).
2. ⏳ Flat-mode: `T` fires an event → `LightReactor` toggles the lamp on a PC, no
   headset. (Built; manual visual confirmation pending — run `flat_test.tscn`.)
3. ⏳ **Device regression**: grab/throw, lever/wheel, secret door still work on the
   Quest. These files are functionally untouched, so risk is low — one pass confirms.
4. ✅ `GameEvents` autoload registered; `vr_main` sets `local_mode` via group lookup.

### 4.5 F0 risks / notes (confirmed during build)
- Additive only — grab/mechanism/secret-door relay NOT refactored onto the bus.
- `--xr-mode off` is REQUIRED for headless runs when the Oculus runtime is live, or
  OpenXR init hangs the main loop before `_process` (cost a couple of cycles here).
- `--check-only --script <file>` hangs the same way (OpenXR) — compile-check by
  `load()`-ing the script inside the `-s` runner instead (see
  `test_interactive_scripts_compile`).
- Use `const X = preload(...)` not `class_name` (headless registry unreliable).
- Keep new diagnostics behind `debug_flags.gd` `Diag.ON`.

---

## 4b. F5 — Health/damage + death/respawn + HUD (BUILT ✅ 2026-06-19)

**Goal:** server-authoritative player health, environmental damage, a death→respawn
loop, and a wrist HUD — the shared dependency for guns (F7) and enemies (F8).

**Authority (the locked decision, realised).** HP is decided ONLY on the server.
- `scripts/health_manager.gd` (`/root/HMVRGame/HealthManager`, group `"health"`, in
  both `main_vr.tscn` and `server_main.tscn`; `server_main.gd` calls its `setup()`).
  Owns `_hp`/`_dead` dicts keyed by peer id. Pure, directly-unit-tested mutations:
  `register / apply_damage / heal / revive` (clamp 0..MAX_HP=100, fire death exactly
  once on the 0-crossing, schedule a `RESPAWN_DELAY=3s` auto-revive).
- Intent path: a client calls `request_damage(amount, source)` → `rpc_id(1,_sv_request)`
  → server gates it (alive? per-(peer,source) cooldown 0.2s — anti-spam, kept OUT of
  `apply_damage` so that stays pure) → `apply_damage`.
- Results broadcast as discrete bus events through the F0 GameEvents relay (server
  `fire` → `_deliver` to all, server-sequenced): `health:changed {peer,hp,max}`,
  `health:died {peer,source}`, `health:respawned {peer,hp,max}`. Single source of
  truth → HUD/feedback derive identically on every peer. (The "damage dealt is a
  discrete event" intent from §2; the *validation* lives in HealthManager, not the
  generic relay.) Offline (local room / flat harness): `setup_offline()` makes the
  node self-authoritative and the bus emits locally.

**Damage source — `scripts/interactables/hazard_volume.gd`** (converter type `hazard`,
`_add_hazard`). An Area3D that hurts the LOCAL player only: detection is client-side
(filters bodies in the new `"player"` group — `locomotion.gd` now adds its CharacterBody
to it), so each client reports just its own damage as intent. `instant=false` →
damage-over-time (`damage_per_second` every `interval`); `instant=true` → one bite on
entry. Translucent-red glow (`material_rgba`) so the danger reads. Hit feedback: `hurt`
SFX (new placeholder) + both-hand haptic — predicted locally; authoritative HP returns
over the bus.

**HUD — `scripts/health_hud.gd`** (NOT converter-generated; it's part of the local
rig like locomotion). World-space green→red fill bar + numeric label; binds to the bus
filtered to the local peer; shows `DOWN` on death. VR: vr_main parents it to the
LeftController as a wrist readout (tilt tuned on device); flat harness parents it to the
camera. Defaults to full HP so the join race (server register arriving before the HUD
connects) reads correctly.

**Death/respawn loop.** `vr_main._on_health_event` (local peer): on `health:died` shows
a status; on `health:respawned` moves the XROrigin back to a SpawnPoint (the authority
already restored HP). Auto-respawn after 3s; in flat mode `K` forces a lethal hit.

**Testing.** `test/test_health.gd` (7 tests, in the runner — total 31/31 green
headless): damage/clamp/die-once, dead-ignores-damage, revive restores+emits, heal
clamp + ignored-while-dead, changed-payload. `tools/health_test.json` → `health-test.tscn`
(a DoT "lava" pit + an instant "spike"); it's now the offline `LOCAL_ROOM_PATH` and the
flat-harness `ROOM_PATH`. Flat keys: `H` -20, `J` +20, `K` lethal→respawn (the harness
has no VR body so hazards don't auto-fire there — keys exercise the manager+HUD+respawn).

**Device test remaining (next session, headset):** wrist HUD readability/placement,
hurt haptic+SFX on entering the pit, death→respawn loop in VR, and a 2-client check that
one player's damage/death does NOT affect the other's HUD (per-peer filtering).

---

## 5. Open questions to revisit
- Persistence scope: what state survives a session (scores yes; puzzle progress?
  inventory?). Ties to the DynamoDB 72h-TTL reward store.
- Server-authoritative promotion timing for puzzle events (only if cheating ever
  matters).
- How much controller simulation the flat harness needs (free-fly + activate may
  be enough; full two-handed sim is more work).
