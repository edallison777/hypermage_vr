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
| **F5** | Health/damage model (server-authoritative) + death/respawn + HUD | F0, F1 | ✅ `caa4752` |
| **F6** | Point scoring + objectives + win/lose + DynamoDB persistence/leaderboard | F0, F5 | ✅ `df23cbb` (F6a) · `a07d84a` (F6b leaderboard, backend live/API-verified) |
| **F7** | Guns: projectiles/beams, VFX, holster, ammo pickups | F0, F1, F5 | ✅ `3b075fa` (hitscan; physical projectiles deferred) |
| **F8** | Enemies: NavMesh, take/inflict damage, spawn waves, difficulty | F0, F5, F7 | ✅ `e2f7b90` (offline device-verified; networked puppet sync with the server test) |
| **F9** | Realistic graphics pass + comfort/accessibility (teleport, vignette, settings) — **plan in §4c** | all | ⬜ |

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

## 4c. F9 — Realistic graphics pass + comfort/accessibility (PLANNED)

**Goal:** make generated worlds look *amazing* on Quest 3 standalone, and ship the
comfort/accessibility options a VR title needs — without abandoning the
converter-generated principle and without dropping below 90fps.

### 4c.0 The platform reframe (why this is an art/technique problem, not an engine one)
On **standalone Quest 3** the GPU is a mobile tile renderer and we run Godot's
`gl_compatibility` (Forward Mobile at best). There is **no realtime GI, no Nanite/Lumen
equivalent, no fat post-process stack** — and Unreal on standalone Quest would face the
same wall (it would give us its *mobile forward* renderer, not Lumen). The Quest titles
that genuinely look amazing (Red Matter 2, Walkabout, Demeo) win on **baked lighting +
disciplined materials + a great sky and fog**, not horsepower. So F9 is an art-direction
and pipeline problem. **Original intent was baked realism** (baked GI = soft bounced light
+ contact shadows, ~free at runtime). **The de-risk probe (§4c.1) killed the *automated*
bake path; the primary is now runtime-lit realism (§4c.3), with a manual editor bake
reserved for a handful of hero scenes only.**

### 4c.1 De-risk RESULT (2026-06-20): headless lightmap baking is NOT feasible in stock Godot
`tools/probe_bake.gd` + `probe_bake2.gd` tested it directly on the installed Godot
**4.6.2-stable** and found, decisively:
- **`RenderingServer.get_rendering_device()` is NULL** under `--headless` AND under
  `--display-driver headless --rendering-driver vulkan` (offscreen Vulkan gives no RD,
  empty video adapter). The GPU lightmapper (`LightmapperRD`) needs an RD → cannot run.
- **`LightmapGI.bake()` is not bound to script** — `has_method("bake")` is false and
  ClassDB lists only `set/get_bake_quality`. Baking is a C++ *editor-plugin* action, not
  reachable from a `-s` runner even with an RD. (`ArrayMesh.lightmap_unwrap()` DOES work
  headlessly — only the bake itself is blocked.)

**Conclusion:** there is no fully-automated, no-window, script-driven lightmap bake in
stock Godot 4.6.2. A `tools/bake_lightmaps.gd` headless stage (the old "one architectural
piece") **cannot exist** without a GDExtension that calls the internal bake (heavy/fragile,
rejected) or a human clicking Bake in the editor.

**Decision (replaces the old §4c.1 plan):**
1. **Primary = runtime-lit realism (§4c.3)** — sky + image-based ambient + ONE directional
   shadow + height fog + `ReflectionProbe`s + good materials + AO baked into textures
   *offline in Blender* (not via Godot lightmaps). 100% converter-generated, no editor, no
   RD-on-PC needed. `ReflectionProbe update_mode = ONCE` bakes **on-device at load** (the
   Quest has a real GPU/RD — the headless-PC limitation doesn't apply there).
2. **Hero-scene bake (optional, accepted bend of §1.3) — IMPLEMENTED (2026-06-20):** the
   converter `--bake` flag emits a *bake-ready* scene so the only editor work is **open →
   select LightmapGI → Bake Lightmaps → Ctrl+S**. All the fiddly prep is headless: primitive
   `BoxMesh.add_uv2=true` gives lightmap UV2 with NO ArrayMesh/unwrap; room shell is
   `gi_mode=STATIC`; sun+omnis are `light_bake_mode=2` (BAKE_DYNAMIC — bake indirect bounce,
   keep realtime direct so dynamic props stay lit); a configured `LightmapGI` node is added.
   For a *small, curated* set of showcase rooms only; the baked lightmap ships as a committed
   artifact. NOT part of the automated generate→ship flow. Try it on
   `scenes/generated/ancient-dungeon-bake.tscn` (regen: `… tools/ancient_dungeon.json --bake
   -o scenes/generated/ancient-dungeon-bake.tscn`). Property names probe-verified
   (`tools/probe_bakeready.gd`). Expect harmless "no UV2" warnings for small dynamic props.
3. VoxelGI/SDFGI remain unavailable on `gl_compatibility`/mobile — out, as before.

Probe scripts kept (`tools/probe_bake.gd`, `tools/probe_bake2.gd`) so the finding is
re-verifiable if we ever change Godot version.

### 4c.2 Materials — PBR, but conditioned for tile GPUs
- StandardMaterial3D with albedo/normal/ORM (occlusion-roughness-metallic packed) — the
  converter already drives material params; extend the ScenePlan material block to carry
  texture refs + roughness/metallic/normal-scale.
- **Tile-GPU discipline:** texture **atlasing** and shared materials to cut draw calls and
  state changes; `KHR_texture_basisu` / compressed (ETC2/ASTC) textures sized to actual
  on-screen need (mostly ≤1–2K); **no per-pixel features we don't need** (parallax, SSS).
  Cull/`gi_mode` set so baked statics never pay realtime lighting.
- **Reflections sell "real" cheaply in VR:** a few `ReflectionProbe`s (baked `ONCE`,
  interior placement from ScenePlan zones) >>> any screen-space trick on this GPU.

### 4c.3 Environment — the cheapest big wins (`sky` + `fog` + probes)
Highest perceived-quality-per-millisecond, and it works even on the no-bake fallback path:
- **HDRI sky** via a panorama `Sky` (Poly Haven CC0 HDRIs, §4c.4). A good sky + image-based
  ambient lifts *everything* and gives free environment reflection for the probes.
- **Height/volumetric-ish fog** (`Environment` fog + depth/height params) for depth and mood —
  cheap, and a classic Quest "looks expensive" trick.
- Tuned `Environment`: ambient light from the sky, mild tonemap (Filmic/ACES), gentle glow
  *only if* it profiles clean on device (fullscreen passes are the tile-GPU tax).
- Converter: a top-level `environment` block in the ScenePlan → emit `WorldEnvironment` +
  `Sky` + fog. Sensible defaults so existing scenes gain a sky/fog with no authoring.

### 4c.4 Asset sourcing + the perf-conditioning pipeline
**Principle: coherence beats variety for looking amazing.** Curated assets anchor the
look; the in-house AI pipeline feeds *variety later*, not the hero look.
- **Curated, in priority order:** **Poly Haven (CC0)** HDRIs + PBR textures first (the sky
  is the biggest single win); **Fab / Quixel Megascans** (free) photoreal materials + hero
  props; Godot Asset Library / Kenney as gap-fillers. Track licences in the asset catalogue.
- **AI pipeline (defer to a stretch):** the existing Phase-7 Meshy→Blender→`asset-catalogue`
  path stays in the plan but is *not* trusted to carry the hero look — its output is too
  inconsistent in poly budget/quality. Route it through the same conditioning stage below
  and use it for bespoke props once the baked look is proven.
- **Perf-conditioning stage (new, shared by curated AND AI assets):** a headless Blender/Godot
  step that **decimates** to a Quest poly budget, generates **LODs**, bakes/atlases textures,
  and **UV2-unwraps** for lightmapping — producing Quest-ready glTF the converter references.
  This is what makes any source asset shippable; it's the asset analogue of the bake stage.

### 4c.5 Comfort / accessibility (independent sub-phase — easy, ship alongside)
Separable from the art work and low-risk; a real VR title needs these:
- **Locomotion comfort:** add a **teleport** option beside the existing smooth locomotion;
  **snap-turn** (configurable degrees) alongside smooth turn; **comfort vignette** (tunnelling)
  on smooth move/turn, intensity configurable.
- **Settings menu** (world-space, converter-independent — part of the rig like the HUD):
  locomotion mode, turn mode, vignette intensity, **handedness** (swap interaction/locomotion
  hands), height calibration, audio volumes (ties to F1 `Audio`/`Haptics`). Persist to a
  user config file.
- **Accessibility:** seated/standing toggle, one-handed-friendly fallbacks where feasible,
  subtitle/caption surface for narration (ties to Phase-8 audio).

### 4c.6 Perf budget & validation (non-negotiable: 90fps)
- Profile **on device**, early and often — the build→reboot→sideload loop (~10 min) applies;
  reboot the Quest after each APK (controller doze wedge, per `godot-controller-oracle`).
- Watch GPU frame time, draw calls, overdraw (transparency/fog are the usual culprits),
  and texture memory. Each visual feature lands only if it profiles clean; back any feature
  out that can't hold 90fps. Maintain the **"art spends the budget last"** rule from §1.

### 4c.7 Testing
- **Off-headset:** the converter's environment/material/conditioning emission runs headless
  and is checkable — generated scene contains the WorldEnvironment/Sky/fog/DirectionalLight/
  ReflectionProbe nodes; conditioned assets meet the poly/texture budget (assert in a
  tool/test). Covered by converter unit tests (a `tools/graphics_test.json` → generated
  scene). The **PC flat harness** renders it (real RD on PC desktop) so the look is viewable
  without a headset.
- **On-headset:** the things only VR shows — baked-light quality and seams, sky/fog read,
  reflection correctness, comfort options (teleport/snap/vignette actually relieve
  discomfort), settings persistence, and the 90fps hold under a populated scene.

### 4c.8 Risks / open decisions
- ~~Headless `LightmapGI` reliability~~ — **RESOLVED (negative): not feasible in stock Godot
  4.6.2** (§4c.1). Primary path is now runtime-lit; this risk is retired.
- **Runtime directional shadow cost** is the new top perf risk — ONE directional shadow is
  the standard mobile-VR approach (cheap), but shadow map size + cull distance must be tuned
  on device. Profile early.
- **`ReflectionProbe` bakes on-device at load** — adds a one-time hitch when a room loads;
  use `update_mode = ONCE`, keep probe count low, accept the load-time cost.
- **AO comes from textures, not Godot lightmaps** — bake AO into the albedo/ORM offline in
  Blender (the conditioning stage, §4c.4). Procedural box rooms get a cheap baked-in vertex
  AO or a subtle SSAO only if it profiles clean.
- **Hero-scene manual bake** is an accepted, conscious bend of §1.3 — limited to a curated
  few showcase rooms, never the automated generate→ship flow.

### 4c.9 Suggested build order (definition of done)
1. **De-risk: DONE** (2026-06-20) — headless bake proven infeasible; pivoted to runtime-lit.
2. **Environment rig: DONE on PC** (2026-06-20) — converter now emits a `WorldEnvironment`
   (procedural sky → sky ambient + sky reflections, ACES tonemap, depth fog), a parameterised
   `SunLight` (one directional shadow), and a per-zone `ReflectionProbe` (`update_mode=ONCE`).
   Optional ScenePlan `environment` block: `preset` (day/dusk/night/cave) + colour/energy/fog
   overrides (`_ENV_PRESETS` + `_resolve_env`). All 61 tests green; all scenes regenerate.
   Rendered `forest-clearing` off-headset via `tools/screenshot_room.gd` (needs a REAL GPU,
   not `--headless`): clear improvement vs the old flat fullbright — soft sky-ambient gradient,
   sky-tinted floor, tonemap, fog. NOTE: enclosed rooms get NO direct sun (walls block it) →
   interiors are sky-ambient + OmniLight lit; the sun shadow only matters for open/sky-facing
   scenes. **Device 90fps check still pending** (the ReflectionProbe on-device load bake + fog
   overdraw are the things to profile). Flat-harness env/sun removed (rooms self-light now).
3. **Materials: DONE on PC** (2026-06-21) — converter `material()`/`pbr_material()` now emit full
   PBR `StandardMaterial3D`: per-surface roughness tiers (floor 0.55 polished / wall 0.82 / ceiling
   0.90 — at the old roughness 1.0 surfaces returned ZERO specular so the sky ambient + reflection
   probe never showed); metallic steel for mechanism arms + gun bodies (roughness 0.35 / metallic
   0.85); self-lit emission on lamp bulbs, torch lenses, ammo pickups. Optional per-zone ScenePlan
   `materials` block ({floor,wall,ceiling} → color/roughness/metallic/emission + albedo/normal/orm
   texture paths + tiling) so step-4 conditioned maps wire in with no further converter work; ORM
   packs occlusion=R/roughness=G/metallic=B. Optional `environment.glow` bloom (default OFF — Quest
   tile-GPU cost; opt-in for hero scenes) makes the emissive parts bloom. All 61 tests green;
   re-rendered `forest_clearing`/`ancient_dungeon` off-headset (glossier floor catching reflection,
   sky-ambient wall gradient, tonemap). **Device 90fps + prop-sheen/glow verify pending** (steel reads
   via the reflection probe; folds into the step-2 device-profile pass).
4. **Asset conditioning stage: DONE on PC** (2026-06-21) — headless Blender pipeline
   `tools/condition_asset.py` (`blender --background --python …`, build-time only, never at
   runtime): decimate-to-tri-budget + UV2 lightmap unwrap + texture-budget downscale → a single
   Quest-ready `.glb` (textures embedded) + a manifest JSON. Runtime LODs are left to Godot's
   glTF importer (meshoptimizer, on by default). `tools/check_asset_budget.py` asserts the
   manifest off-headless (CI/test). First hero asset: **Poly Haven `treasure_chest` (CC0)** —
   conditioned **103,330 → 4,000 tris**, UV2 added, 1k ARM(occlusion/roughness/metallic)+diff+normal
   maps (maps straight onto the step-3 ORM material support). Converter gained a `prop`/`model`
   interactable type (instances an imported `.glb`, optional box collision) + `tools/graphics_test.json`
   showcase scene. Rendered off-headset: the PBR chest reads photoreal against the runtime-lit room —
   the big jump over primitive boxes. Also fixed `tools/screenshot_room.gd` (it set the camera
   transform in `_initialize` before nodes were in-tree → silently stayed at the origin, making every
   prior preview unrepresentative; now positions in `_process`). 61/61 tests green. Committed: `.glb`
   + manifest + CREDITS (raw `asset_src/` gitignored, reproducible). Blender 5.1.2 installed via winget
   (`C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`) — new build-time dep.
5. **Comfort/accessibility sub-phase: DONE on PC** (2026-06-21) — new `Comfort` autoload
   (`scripts/comfort_settings.gd`) holds all settings, persists to `user://comfort.cfg`, emits
   `changed`; comfort-first defaults (snap-turn + vignette ON). `locomotion.gd` rewritten to read
   it: **snap-turn** (debounced flick, configurable 15/30/45/60°) vs smooth; **teleport** locomotion
   (parabolic arc off the move hand, walkable-layer target, ring marker, confirm-on-release) vs smooth
   move; **handedness** (move/turn hand swap); **height offset + seated** lift; feeds the
   **comfort vignette** (`scripts/comfort_vignette.gd` — camera-attached radial shader, tunnels the
   periphery on move/turn, eased, strength-scaled). World-space **settings menu**
   (`scripts/comfort_menu.gd`, in `main_vr.tscn`): A/X toggles a panel of fingertip-poke buttons that
   `cycle()` each setting — fully LOCAL (off the networked bus), `ui_click` + haptic feedback. Master
   volume → AudioServer Master bus. 74/74 tests green (13 new in `test/test_comfort.gd`: cycle/persist/
   dict/snap-radians/vignette-mapping/menu-format). All Comfort/vignette/menu/locomotion scripts
   compile-checked; `main_vr.tscn` loads. **Device-verify pending** (teleport aim, snap comfort,
   vignette feel, menu poke, settings persistence) — folds into the F9 device pass.
6. **Profile, tune, hold 90fps**; commit per the usual recipe; device-verify.

---

## 5. Open questions to revisit
- Persistence scope: what state survives a session (scores yes; puzzle progress?
  inventory?). Ties to the DynamoDB 72h-TTL reward store.
- Server-authoritative promotion timing for puzzle events (only if cheating ever
  matters).
- How much controller simulation the flat harness needs (free-fly + activate may
  be enough; full two-handed sim is more work).
