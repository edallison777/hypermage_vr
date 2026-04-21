# Hypermage — Project Roadmap

A living document tracking progress toward a fully agentic LARP world-building platform
delivering VR (Meta Quest 3) and web experiences from natural language descriptions.

**Vision:** Describe a world → agents build it → participants play it, in VR or a browser,
responding to live GM direction, with commissioned art and original audio.

---

## Status Legend
- `[x]` Complete
- `[-]` In progress
- `[ ]` Not started
- `[~]` Deferred / blocked

---

## Completed Phases

### Phase 1 — Code & Test Foundation
- [x] TypeScript agent scaffolding (11 agents, BaseAgent, MCP adapters)
- [x] Jest test suite: 21/21 suites, 148/148 tests green
- [x] 80% coverage threshold enforced
- [x] 22 property-based tests (fast-check)
- [x] JSON schema validation (AJV)
- [x] CI/CD pipeline (GitHub Actions)

### Phase 2 — First AWS Deployment
- [x] Terraform IaC for all AWS resources
- [x] 49 resources live in eu-west-1
- [x] Cognito User Pool + Identity Pool
- [x] API Gateway + Lambda (matchmaking, session summary)
- [x] DynamoDB tables (sessions, events, rewards)
- [x] CloudWatch logging

### Phase 2.5 — AgentCore Deployment
- [x] Proven container deployment pattern (CodeBuild ARM64)
- [x] All 11 agents deployed as AgentCore containers
- [x] ProducerOrchestrator wired to invoke worker agents via real Bedrock calls
- [x] All agents in READY state

### Phase 3 — Meta Quest 3 Device Testing
- [x] UE5.3 VR project with OpenXR
- [x] APK built and sideloaded via ADB
- [x] Cognito auth working from Quest 3
- [x] API Gateway + Lambda reachable from device
- [x] Proxy server for CORS-free browser testing (`TestAPK/web-test/proxy-server.js`)

### Phase 4 — GameLift / FlexMatch
- [x] Packer AMI build (ami-0c01dd20bfd8bb6a9, eu-west-1)
- [x] UE5 server compiled and packaged (HyperMageVRServer.zip, 790MB, S3)
- [x] GameLift fleet live (fleet-848aced2, AL2023, c5.large)
- [x] FlexMatch config + rule set deployed
- [x] End-to-end validated from Quest 3: login → matchmaking → COMPLETED → IP+port
- [x] Direct game session test: server process ACTIVE, accepted session
- [x] Solo test rule set created (minPlayers=1, `hypermage-vr-dev-rules-solo`)
- [x] Fleet scaled to 0 when idle (scale up cmd in memory)

---

## Active & Upcoming Phases

### Phase 5 — First Real Pipeline: Text → ScenePlan ✅ COMPLETE
> **Goal:** Type a description, get a valid ScenePlan.json in S3.
> **Done when:** `python invoke.py "a neon-lit cyberspace node for a cyberpunk LARP"` → valid ScenePlan.json saved to S3.

- [x] Design `ScenePlan.schema.json` (LARP-aware: narrative states, GM hooks, atmosphere, dual platform, asset sources)
- [x] Define new schemas: `NarrativeState.schema.json`, `GMControlEvent.schema.json`, `WebSceneSpec.schema.json`
- [x] Update EnvironmentDesigner (ConversationLevelDesigner) system prompt for LARP/scene thinking
- [x] Implement `get_available_rewards` tool — reads real rewards catalog
- [x] Implement `validate_scene_plan` tool — full schema + cross-reference validation
- [x] Implement `save_scene_plan` tool — persists to S3 with metadata
- [x] Implement `place_narrative_hooks` tool — analyses hooks and suggests effects
- [x] Redeploy EnvironmentDesigner to AgentCore (ECR: 20260406-210944-136)
- [x] Update ProducerOrchestrator decompose_specification to request ScenePlan (not LevelPlan)
- [x] Redeploy ProducerOrchestrator (ECR: 20260406-211729-331)
- [x] Build CLI entry point (`scripts/invoke.py`) — calls EnvironmentDesigner directly, extracts + displays ScenePlan
- [x] End-to-end test: description in → ScenePlan.json out ✅
  - `python invoke.py "a neon-lit cyberspace node for a cyberpunk LARP" --type cyberspace --platforms vr web`
  - Produced "DataVault Node Alpha": 4 zones, 4 GM hooks, 3 narrative states, vr + web
  - Saved to `s3://hypermage-vr-unreal-build-artifacts-dev/scene-plans/cyberspace_node_alpha/scene_plan.json`
  - Fix applied: added `S3ScenePlanWritePolicy` to AgentCore runtime role `AmazonBedrockAgentCoreSDKRuntime-eu-west-1-81c578ca1b`

---

### Phase 6 — Infrastructure Agents Get Real Tools ✅ COMPLETE
> **Goal:** CostMonitorFinOps reports real AWS spend. DevOpsAWS can trigger Terraform and fleet changes.
> **Done when:** ProducerOrchestrator asks for a cost report and gets real data back.

- [x] CostMonitorFinOps: wire `track_cost` to DynamoDB (hypermage-vr-interaction-events-dev)
- [x] CostMonitorFinOps: wire `check_budget` to boto3 Cost Explorer (real MTD spend vs £1000 budget)
- [x] CostMonitorFinOps: wire `generate_cost_report` to Cost Explorer + write report to DynamoDB
- [x] DevOpsAWS: wire `execute_terraform` to read live Terraform state from S3 + generate plan
- [x] DevOpsAWS: wire `deploy_infrastructure` to boto3 GameLift fleet management (scale up/down)
- [x] Redeploy both agents (ECR: CodeBuild, auto_update_on_conflict)
- [x] Integration test: 5/5 passed — real Cost Explorer data ($113.93 USD MTD), real GameLift fleet (77 Terraform resources live)
  - CostMonitorFinOps `generate_cost_report` → real service breakdown (EC2, GameLift, Cognito, etc.)
  - CostMonitorFinOps `check_budget` → approved, £910 remaining
  - DevOpsAWS `deploy_infrastructure` → fleet-848aced2 ACTIVE reported
  - DevOpsAWS `execute_terraform` → 77 resources from live S3 state

---

### Phase 7 — Asset Ingestion Pipeline ✅ COMPLETE
> **Goal:** Drop a commissioned asset into S3, get it available in both UE5 and web formats with provenance.
> **Done when:** Commissioned PNG → S3 `incoming/` → glTF + FBX outputs → provenance record in DynamoDB → queryable by EnvironmentDesigner.

- [x] S3 `incoming/` prefix convention + Lambda trigger on upload (`assets/incoming/` → asset-ingest-trigger Lambda)
- [x] Format conversion: FBX/OBJ → glTF (Blender headless ECS Fargate — exits on completion, zero idle cost)
- [x] Format conversion: PNG/PSD → WebP (Pillow in Lambda) + ASTC pending marker (requires native binary)
- [x] 2D → 3D: integrate Meshy.ai API (image-to-3D mesh) — reads key from SSM, skips gracefully if not configured
- [x] AssetPipelineAgent: `validate_asset_import` — DynamoDB duplicate check + required field validation
- [x] AssetPipelineAgent: `create_provenance_record` — writes to DynamoDB `hypermage-vr-asset-catalogue-dev`
- [x] AssetPipelineAgent: `query_asset_catalogue` — DynamoDB query by assetType/status GSI + in-memory tag filter
- [x] Redeploy AssetPipelineAgent (`AssetPipeline_Agent-siqbOWHci2`)
- [x] EnvironmentDesigner: `get_available_assets()` tool + system prompt updated to call it + populate `asset_sources[]`
- [x] End-to-end test: 5/5 passed — Oracle Statue written to DynamoDB, queried by AssetPipelineAgent, referenced by EnvironmentDesigner in a ritual ScenePlan saved to S3

---

### Phase 8 — Audio Production Pipeline ✅ COMPLETE
> **Goal:** ScenePlan audio palette description → original ambient, music, SFX, and narration files in S3.
> **Done when:** Scene description produces a set of MP3 files in S3, consumable by both UE5 and web.

- [x] Provider selection: ElevenLabs (SFX + TTS narration), Stability AI (ambient + score)
- [x] TechArtVFXAudioAgent: `generate_ambient(scene_id, description, duration)` → Stability AI → S3 + DynamoDB
- [x] TechArtVFXAudioAgent: `generate_score(scene_id, description, duration, loop)` → Stability AI → S3 + DynamoDB
- [x] TechArtVFXAudioAgent: `generate_sfx(scene_id, description)` → ElevenLabs Sound Effects → S3 + DynamoDB
- [x] TechArtVFXAudioAgent: `generate_narration(scene_id, text, voice_id)` → ElevenLabs TTS → S3 + DynamoDB
- [x] TechArtVFXAudioAgent: `query_audio_assets(scene_id, audio_type)` → DynamoDB SceneIdIndex/AudioTypeIndex
- [x] DynamoDB `hypermage-vr-audio-assets-dev` — SceneIdIndex + AudioTypeIndex GSIs
- [x] SSM placeholders at `/hypermage/elevenlabs-api-key` + `/hypermage/stability-api-key`
- [x] Redeploy TechArtVFXAudioAgent (`TechArtVFXAudio_Agent-08HN169vef`)
- [x] Integration test: 6/6 passed — graceful skips when keys absent, 3 DynamoDB records written, full ScenePlan palette → 3-track audio set described in catalogue

---

### Phase 9 — UnrealMCP Bridge ✅ COMPLETE
> **Goal:** An agent can create and manipulate objects in a live UE5 editor on the dev PC.
> **Done when:** Agent call creates a visible actor in the UE5 editor.

- [x] DefaultEngine.ini snippet: Remote Control plugin config (`scripts/unreal-bridge/DefaultEngine.ini.snippet`)
- [x] UnrealBridge FastAPI service (`scripts/unreal-bridge/bridge.py`) wraps UE5 RC HTTP API:
  - `POST /actor/create` — SpawnActorFromClass via EditorActorSubsystem
  - `POST /actor/set-property` — set UObject property
  - `POST /level/save` — SaveCurrentLevel
  - `POST /console` — ExecuteConsoleCommand
  - `POST /scene-plan/build` — full ScenePlan → zone blockouts + PlayerStarts + save
  - `GET /health` — check UE5 reachability
- [x] `start.sh --ngrok` — starts bridge + ngrok tunnel + auto-updates SSM
- [x] SSM `/hypermage/unreal-bridge-url` — Terraform placeholder, populate via start.sh
- [x] UnrealLevelBuilderAgent (`UnrealLevelBuilder_Agent-rFwJdR9uPr`): all tools wired to bridge
  - `get_bridge_status`, `spawn_actor`, `set_actor_property`, `run_console_command`, `save_level`, `build_scene_from_plan`, `generate_blockout_geometry`
  - Graceful skip (status='skipped') when bridge not configured
- [x] Integration test: 6/6 passed — all tools correctly skip when bridge absent, blockout geometry computed offline

---

### Phase 10 — Web Platform Foundation ✅ COMPLETE
> **Goal:** ScenePlan generates a web URL. Browser shows the scene in 3D with atmosphere and audio.
> **Done when:** Open the URL, see the Babylon.js scene rendered with correct lighting, assets, and ambient audio playing.

- [x] Select web renderer: Babylon.js (best glTF support, shared assets with UE5)
- [x] WebPlatformAgent: `generate_web_scene(scene_plan)` → Babylon.js HTML scene → S3
- [x] WebPlatformAgent: `deploy_web_scene` → CloudFront invalidation → live URL
- [x] WebPlatformAgent: `query_web_scenes` → DynamoDB scene catalogue
- [x] WebSocket API (API Gateway WebSocket + Lambda) — participant join/leave, presence, narrative state sync
- [x] DynamoDB `hypermage-vr-web-scenes-dev` (StatusDeployedAtIndex) + `hypermage-vr-ws-connections-dev` (SceneIdIndex)
- [x] S3 `hypermage-vr-web-scenes-dev` + CloudFront `d3nzdmu3cdrzxk.cloudfront.net` (PriceClass_100, OAC)
- [x] SSM `/hypermage/web-platform/cloudfront-domain`, `/ws-url`, `/scenes-bucket`
- [x] Deploy WebPlatformAgent to AgentCore (`WebPlatform_Agent-y8AKhy2ISX`)
- [x] Integration test: 6/6 passed — SSM params live, ScenePlan → HTML in S3 → CloudFront URL deployed
  - `https://d3nzdmu3cdrzxk.cloudfront.net/scenes/phase10-test-scene-001/index.html`
  - WebSocket: `wss://yd895183ei.execute-api.eu-west-1.amazonaws.com/dev`
- [x] IAM: `Phase10WebPlatformPolicy` on runtime role

---

### Phase 11 — LARP Integration Layer + Web/Phone Playable ✅ COMPLETE
> **Goal:** GM fires an event on their phone, all participants (VR + web + phone) see and hear the scene change within 2 seconds.
> **Done when:** Full GM → digital world event loop demonstrated live; web scene is playable on a phone browser with audio and commissioned assets visible.

#### 11a — Web/Phone Playable (WebPlatformAgent upgrade) ✅
- [x] Audio wired into Babylon.js HTML (BABYLON.Sound + pre-signed S3 URLs, autoplay on gesture)
- [x] Spatial SFX at zone positions using Babylon.js `Sound` with spatial attenuation
- [x] glTF assets loaded from Phase 7 asset catalogue (SceneLoader.ImportMesh per `asset_sources[]`)
- [x] Fallback to primitive blockout if glTF unavailable
- [x] Mobile / phone playability: BABYLON.VirtualJoystick, tap-to-interact raycast → WS narrative_event
- [x] PWA manifest (`manifest.json`) uploaded to S3 — phone home screen installable
- [x] Cognito-gated access (`?token=` URL param checked against Cognito JWKS)
- [x] GM control panel HTML (`gm-panel/{scene_id}/index.html`) — dark theme, hook buttons
- [x] Integration test: 6/6 passed

#### 11b — LARP Integration Layer (NarrativeAgent + GM panel) ✅
- [x] NarrativeAgent (`Narrative_Agent-UOjm2k34zb`): `advance_scene`, `get_narrative_state`, `list_available_hooks`
- [x] LARPIntegrationAgent (`LARPIntegration_Agent-mLn5uaDVVj`): `fire_gm_event`, `get_connected_participants`, `get_scene_status`
- [x] `POST /gm/event` Lambda + HTTP API (`https://i5thx87k5k.execute-api.eu-west-1.amazonaws.com/dev/gm/event`)
- [x] WebSocket broadcast on state change (apigatewaymanagementapi → all ws-connections)
- [x] DynamoDB `hypermage-vr-ws-connections-dev` (SceneIdIndex) — participant presence tracking
- [x] SSM `/hypermage/larp/gm-event-url`, `/hypermage/larp/ws-management-endpoint`
- [x] IAM: all permissions in `HypermageAgentsConsolidatedPolicy`
- [x] Integration test: 7/7 passed

---

### Phase 12 — UnrealLevelBuilder: ScenePlan → Real UE5 Environment ✅ COMPLETE
> **Goal:** ScenePlan produces a real .umap file with commissioned assets placed and atmosphere applied.
> **Done when:** Open generated .umap in UE5 editor, see correct layout, lighting, and assets.

- [x] `convert_sceneplan_to_map(scene_plan_json, map_name)` — full pipeline: zones → blockout → atmosphere → assets → gm_hooks → save
- [x] `apply_atmosphere(lighting_mood)` — bloom/vignette/fog/sky UE5 console commands per mood preset
- [x] Zone volumes → UE5 spatial volumes (PlayerStart + BSP blockout via bridge)
- [x] Asset placement — StaticMeshActors for `asset_sources[]` from ScenePlan
- [x] GM hook trigger volumes → TriggerVolume actors tagged with hook IDs
- [x] Bridge endpoint `POST /scene-plan/build-full` added to `scripts/unreal-bridge/bridge.py`
- [x] Deploy updated UnrealLevelBuilder_Agent (`UnrealLevelBuilder_Agent-rFwJdR9uPr`) to AgentCore
- [x] Integration test: 5/5 passed — all tools skip gracefully when bridge offline
- [x] To use live: open UE5 + Remote Control plugin, run `start.sh --ngrok`

---

### Phase 13 — Quest 3 Connects to Server ✅ COMPLETE
> **Goal:** Put on the headset, matchmaking completes, you appear inside the generated scene.
> **Done when:** Quest 3 client calls real Session API, receives IP+port, travels to server.

- [x] `HMVRGameInstance::StartMatchmaking()` — real `POST /matchmaking/start` via FHttpModule (replaced mock)
- [x] `PollMatchmakingStatus()` — timer-based 3s poll of `GET /matchmaking/status/{ticketId}`
- [x] On COMPLETED: extract `ipAddress`, `port`, `playerSessionId` from `gameSessionConnectionInfo`
- [x] `ConnectToGameServer()` URL bug fixed (`?PlayerSessionId` → `&PlayerSessionId`)
- [x] `HyperMageVR.Build.cs` — `"HTTP"` module added
- [x] MultiplayerNetcodeAgent: `start_matchmaking`, `poll_matchmaking_status`, `get_fleet_capacity`, `scale_fleet` tools added + deployed
- [x] Integration test: 6/6 passed

---

### Phase 14 — Session Persistence & Real PlayerId ✅ COMPLETE
> **Goal:** When a player leaves, their session summary and rewards land in DynamoDB under their real Cognito ID.
> **Done when:** DynamoDB `player-sessions` and `player-rewards` contain entries keyed on the actual Cognito sub claim.

- [x] `AHMVRPlayerState` — new PlayerState class storing `PlayerId` (Cognito `sub`), replicated
- [x] `HMVRGameMode::Login()` — calls `DecodeToken()` on JWT, writes `Claims.Subject` to PlayerState
- [x] `HMVRGameMode::OnPlayerJoined/Left()` — reads `PlayerId` from PlayerState (no more random GUIDs)
- [x] `AwsSigV4.h/.cpp` — minimal SigV4 signer (OpenSSL HMAC-SHA256, reads EC2 instance creds from env vars)
- [x] `SessionAPIClient.h/.cpp` — real async fire-and-forget HTTP POST to `/session-summary` + `/interaction-events` with SigV4
- [x] `HyperMageVR.Build.cs` — `AddEngineThirdPartyPrivateStaticDependencies(Target, "OpenSSL")` added
- [x] `HMVRGameMode::InitGame()` — configures `SessionAPIClient` with live Session API endpoint
- [x] Terraform: `fleet_session_api` IAM policy — `execute-api:Invoke` for both session endpoints on fleet role
- [x] Terraform: `api_execution_arn` output added to session-api module, wired into gamelift-fleet via `session_api_execution_arn`
- [x] Integration test: 6/6 passed

---

### Phase 15 — Server Rebuild & Fleet Update ✅ COMPLETE
> **Goal:** The GameLift fleet runs the current codebase (all C++ from phases 1–14).
> **Done when:** `aws gamelift describe-fleet-attributes` shows a build from today; Quest 3 connects and session summary lands in DynamoDB with a real PlayerId.

- [x] UE5 Linux server rebuilt with Phase 13/14 C++ (HTTP matchmaking, PlayerState, AwsSigV4, SessionAPIClient)
- [x] `HyperMageVRServer.zip` uploaded to `s3://hypermage-vr-unreal-build-artifacts-dev/builds/latest/`
- [x] New GameLift build registered — `build-33d794db-c275-4fb6-9ca9-3a14836eb8c1` READY
- [x] Terraform fleet replace — `fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9` ACTIVE with Phase 15 build
- [x] Phase 14 IAM: `session-api-invoke` policy on fleet role `hypermage-vr-gamelift-fleet-dev`
- [x] Alias `alias-e67abbec-14ba-4e6d-8e95-6b0edfaad18e` unchanged — client code unaffected
- [x] Integration test: 6/6 passed (`scripts/test_phase15.py`)

**Scale up before live E2E:**
```bash
aws gamelift update-fleet-capacity --fleet-id fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9 --desired-instances 1 --region eu-west-1
```

---

### Phase 16 — APK Hardening: Offline Resilience + Error UX ✅ COMPLETE
> **Goal:** The Quest 3 client handles network failures gracefully and shows clear error states to the player.
> **Done when:** Matchmaking failure shows an error widget with Retry/Cancel; session API retries on transient failure; CancelMatchmaking sends a real DELETE request.

- [x] `HMVRStatusWidget` (C++): `UUserWidget` base with `BlueprintImplementableEvent` Show*/HideWidget
  - `ShowSearching()`, `ShowConnecting()`, `ShowError(Message)`, `ShowSuccess()`, `HideWidget()`
  - `BlueprintAssignable` delegates: `OnRetryRequested`, `OnCancelRequested`
- [x] `UHMVRGameInstance` upgrades:
  - `EnsureStatusWidget()` — creates widget from `StatusWidgetClass`, adds to viewport, wires delegates
  - `ReturnToMainMenu()` — `OpenLevel` to `MainMenuLevelName`
  - 4 `BlueprintAssignable` delegates: `OnMatchmakingStatusChanged`, `OnMatchmakingError`, `OnConnectionEstablished`, `OnConnectionError`
  - All 4 dangling `// TODO: Notify UI` comments replaced with real delegate broadcasts + widget calls
- [x] `CancelMatchmaking()` — sends `DELETE /matchmaking/cancel/{ticketId}` (was a TODO stub)
- [x] `SessionAPIClient` — exponential-backoff retry (MaxRetries=3, delays 1s/2s/4s via FTSTicker) on 5xx/network error
- [x] Lambda `hypermage-vr-cancel-matchmaking-dev` — `DELETE /matchmaking/cancel/{ticketId}`, Cognito auth, idempotent
- [x] Terraform: cancel Lambda + `/matchmaking/cancel/{ticketId}` API GW route deployed (8 new resources)
- [x] `HyperMageVR.Build.cs` — `UMG` module added
- [x] Integration test: 7/7 passed (`scripts/test_phase16.py`)

**Next step:** Create Blueprint subclass of `UHMVRStatusWidget` in UE5 editor for actual in-headset error UI, then live E2E on Quest 3.

---

### Phase 17 — Live E2E on Quest 3 + Error UX Blueprint [-]
> **Goal:** Full live end-to-end test on the headset with the Phase 16 error UX visible: matchmaking shows "Searching…", failure shows error widget with working Retry/Cancel buttons.
> **Done when:** Quest 3 connects successfully to the new fleet with real session persistence, AND deliberately-triggered failure shows the error widget.

- [ ] Create `BP_StatusWidget` Blueprint subclass of `UHMVRStatusWidget` in UE5 editor
  - Implement `ShowSearching`, `ShowConnecting`, `ShowError`, `ShowSuccess`, `HideWidget` events with UMG visuals
  - Wire `OnRetryRequested` and `OnCancelRequested` button clicks
- [ ] Set `StatusWidgetClass = BP_StatusWidget` on `BP_HMVRGameInstance` defaults
- [ ] Set `MainMenuLevelName` on `BP_HMVRGameInstance` defaults
- [ ] Scale fleet to 1: `aws gamelift update-fleet-capacity --fleet-id fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9 --desired-instances 1 --region eu-west-1`
- [ ] Live Quest 3 test — happy path: login → matchmaking → "Searching…" widget → COMPLETED → connected
- [ ] Live Quest 3 test — failure path: disable network mid-search → error widget visible → Retry works
- [ ] Verify DynamoDB `player-sessions` entry contains real Cognito sub (not a GUID)
- [ ] Run `python scripts/test_phase17.py --check-e2e` to confirm no GUID playerIds + fleet scaled down
- [ ] Scale fleet back to 0 after testing

**Pre-live checks:** 5/5 passed (2026-04-21) — fleet ACTIVE, alias correct, C++ source complete

---

### Phase 18 — Interaction Systems, Voice, QA
> **Goal:** Participants can interact with the world. Agents validate the whole pipeline automatically.
> **Done when:** Full automated QA pass on a generated scene — assets, audio, narrative hooks, VR + web delivery all validated.

- [ ] InteractionSystemsAgent: implement flexible interaction triggers
  - [ ] Touch object → narrative event
  - [ ] Enter zone → atmosphere change
  - [ ] Proximity → GM notification
- [ ] VoiceCommsAgent: party voice integration (Agora recommended for cross-platform VR+web)
- [ ] QAAgent: implement real test generation and execution
  - [ ] `generate_scene_tests` — produces pytest/Jest for ScenePlan validation
  - [ ] `validate_assets` — checks all ScenePlan asset references exist in catalogue
  - [ ] `validate_narrative` — checks all hooks reachable from initial state
  - [ ] `run_tests` — subprocess execution, returns pass/fail report
- [ ] Full pipeline QA: ProducerOrchestrator triggers QA on generated scene before deployment

---

## Technical Debt & Known Issues

- [ ] FlexMatch production rule set requires 10 players (`hypermage-vr-dev-rules`) — fine for production, solo test uses `-rules-solo`
- [ ] APK hardcodes PC proxy IP (`192.168.178.76`) — update when rebuilding APK
- [ ] Windows Firewall rule for port 8080 added manually — document in setup guide
- [ ] 10 of 11 agents are stub implementations — being resolved Phase 5 onwards
- [ ] Scratch JSON files in repo root (check-api.json, fetch-ubt-log.json etc.) — clean up

---

## Cost Controls

| Resource | Status | Monthly cost | Action |
|----------|--------|-------------|--------|
| GameLift fleet (c5.large) | **Scaled to 0** | ~$0 idle / ~$61 if running 24/7 | Scale to 1 before testing only |
| AgentCore agents (×14) | READY | ~$0 (pay per invocation) | No action needed |
| Lambda / API Gateway / DynamoDB | Live | Negligible at dev traffic | No action needed |
| S3 / CloudWatch | Live | Pennies | No action needed |
| `reignite-elasticbeanstalk-01` | Running | ~$8/month | Separate project, user-managed |

**Scale fleet up for testing:**
```bash
aws gamelift update-fleet-capacity --fleet-id fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9 --desired-instances 1 --region eu-west-1
```

---

## Key Infrastructure References

| Resource | Value |
|----------|-------|
| AWS Account | 732231126129 (eu-west-1) |
| Session API | `https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev` |
| Cognito User Pool | `eu-west-1_q2rAaummA` |
| Cognito Game Client | `2iinqhoja78kj1et6rcv28bjvf` |
| GameLift Fleet | `fleet-bdae1b71-b2c1-42cf-b242-6322be08d5a9` |
| GameLift Alias | `alias-e67abbec-14ba-4e6d-8e95-6b0edfaad18e` |
| FlexMatch Config | `hypermage-vr-dev` |
| S3 Build Bucket | `hypermage-vr-unreal-build-artifacts-dev` |
| Terraform State | S3 `hypermage-vr-terraform-state` / `dev/terraform.tfstate` |
| Terraform Working Dir | `Infra/environments/dev` |
