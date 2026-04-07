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

### Phase 7 — Asset Ingestion Pipeline
> **Goal:** Drop a commissioned asset into S3, get it available in both UE5 and web formats with provenance.
> **Done when:** Commissioned PNG → S3 `incoming/` → glTF + FBX outputs → provenance record in DynamoDB → queryable by EnvironmentDesigner.

- [ ] S3 `incoming/` prefix convention + Lambda trigger on upload
- [ ] Format conversion: FBX/OBJ → glTF (Blender headless on Lambda/ECS)
- [ ] Format conversion: PNG/PSD → WebP + ASTC (ImageMagick/Basis Universal)
- [ ] 2D → 3D: integrate Meshy.ai API (image-to-3D mesh) for flat concept art
- [ ] AssetPipelineAgent: implement `validate_asset_import` against AssetSpec schema
- [ ] AssetPipelineAgent: implement `create_provenance_record` writing to DynamoDB
- [ ] AssetPipelineAgent: implement `query_asset_catalogue` — list available assets by type/tag
- [ ] Redeploy AssetPipelineAgent
- [ ] EnvironmentDesigner can reference catalogue assets in ScenePlan `asset_sources[]`
- [ ] End-to-end test: upload asset → both formats in S3 → provenance in DynamoDB → appears in catalogue

---

### Phase 8 — Audio Production Pipeline
> **Goal:** ScenePlan audio palette description → original ambient, music, SFX, and narration files in S3.
> **Done when:** Scene description produces a set of OGG files (ambient loop, score, SFX pack) in S3, consumable by both UE5 and web.

- [ ] Evaluate and select audio AI provider(s): ElevenLabs Sound Effects, Stability Audio, AudioCraft
- [ ] TechArtVFXAudioAgent: implement `generate_ambient(description)` → OGG to S3
- [ ] TechArtVFXAudioAgent: implement `generate_score(description, duration, loop)` → OGG to S3
- [ ] TechArtVFXAudioAgent: implement `generate_sfx(description)` → short OGG to S3
- [ ] TechArtVFXAudioAgent: implement `generate_narration(text, voice_id)` → OGG to S3 (ElevenLabs TTS)
- [ ] Audio metadata schema — track generated assets with scene association in DynamoDB
- [ ] Redeploy TechArtVFXAudioAgent
- [ ] End-to-end test: ScenePlan with `audio_palette` → full audio asset set in S3

---

### Phase 9 — UnrealMCP Bridge
> **Goal:** An agent can create and manipulate objects in a live UE5 editor on the dev PC.
> **Done when:** Agent call creates a visible actor in the UE5 editor.

- [ ] Enable UE5 Remote Control Plugin + HTTP API in DefaultEngine.ini
- [ ] Build `UnrealBridge` Python FastAPI service (dev PC)
  - [ ] `POST /actor/create` — spawn actor by class at transform
  - [ ] `POST /actor/set-property` — set property on actor
  - [ ] `POST /level/save` — save current level
  - [ ] `POST /console` — run UE5 console command
- [ ] Expose bridge to agents (ngrok tunnel or fixed LAN)
- [ ] UnrealLevelBuilderAgent: replace stubs with real HTTP calls to bridge
- [ ] Smoke test: agent spawns a cube in UE5

---

### Phase 10 — Web Platform Foundation
> **Goal:** ScenePlan generates a web URL. Browser shows the scene in 3D with atmosphere and audio.
> **Done when:** Open the URL, see the Babylon.js scene rendered with correct lighting, assets, and ambient audio playing.

- [ ] Select web renderer: Babylon.js (recommended — best glTF support, shared assets with UE5)
- [ ] WebPlatformAgent: implement `generate_web_scene(scene_plan)` → Babylon.js scene JSON
- [ ] WebPlatformAgent: implement `deploy_web_scene` → S3 static + CloudFront distribution
- [ ] WebSocket game server — Node.js on ECS Fargate
  - [ ] Participant join/leave
  - [ ] Shared position/presence
  - [ ] Narrative state sync (DynamoDB → push to all clients)
- [ ] Shared session — VR and web participants in the same DynamoDB session record
- [ ] Deploy WebPlatformAgent to AgentCore
- [ ] End-to-end test: ScenePlan → web URL → scene visible in browser

---

### Phase 11 — LARP Integration Layer
> **Goal:** GM fires an event on their phone, all participants (VR + web) see the scene change within 2 seconds.
> **Done when:** Full GM → digital world event loop demonstrated live.

- [ ] NarrativeAgent: narrative state machine implementation
  - [ ] Scene states and transitions defined in ScenePlan
  - [ ] `advance_scene(hook_name)` — fires transition, updates DynamoDB state
  - [ ] `get_narrative_state()` — current state, available hooks, unlocked content
- [ ] GM control panel (S3-hosted web page, Cognito-gated)
  - [ ] Current narrative state display
  - [ ] Hook buttons (fire any defined `gm_hook`)
  - [ ] Connected participant count (VR + web)
- [ ] LARPIntegrationAgent: external event API
  - [ ] `POST /gm/event` endpoint (API Gateway) — accepts signed events from physical props, external LARP software, or GM app
  - [ ] WebSocket push to all connected clients on event
- [ ] Deploy NarrativeAgent and LARPIntegrationAgent to AgentCore
- [ ] End-to-end test: GM fires hook → web client receives narrative state change in <2s

---

### Phase 12 — UnrealLevelBuilder: ScenePlan → Real UE5 Environment
> **Goal:** ScenePlan produces a real .umap file with commissioned assets placed and atmosphere applied.
> **Done when:** Open generated .umap in UE5 editor, see correct layout, lighting, and assets.

- [ ] UnrealLevelBuilderAgent: implement `convert_sceneplan_to_map` via bridge
- [ ] Zone volumes → UE5 spatial volumes / BSP blockout
- [ ] Asset placement — place ScenePlan `asset_sources` references as StaticMeshActors
- [ ] Atmosphere — apply sky/lighting/post-process from ScenePlan `atmosphere` spec
- [ ] Player spawns → PlayerStart actors
- [ ] GM hook trigger volumes → TriggerBox actors with event tags
- [ ] Level save + package via bridge
- [ ] End-to-end test: ScenePlan.json → packaged .umap ready for server build

---

### Phase 13 — Quest 3 Connects to Server
> **Goal:** Put on the headset, matchmaking completes, you appear inside the generated scene.
> **Done when:** Quest 3 APK connects to game server, player visible in generated level.

- [ ] APK: on matchmaking COMPLETED, call `OpenLevel(IP:Port)` to connect to server
- [ ] Server: verify `OnStartGameSession` handles player joins (not just ProcessReady)
- [ ] Basic player representation (pawn) visible to connected participants
- [ ] VR + web participant presence synchronised via DynamoDB/WebSocket
- [ ] Rebuild and sideload APK
- [ ] Live test: Quest 3 + browser, both in same scene

---

### Phase 14 — Interaction Systems, Voice, QA
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
aws gamelift update-fleet-capacity --fleet-id fleet-848aced2-ac8f-405a-b120-43f4f3904983 --desired-instances 1 --region eu-west-1
```

---

## Key Infrastructure References

| Resource | Value |
|----------|-------|
| AWS Account | 732231126129 (eu-west-1) |
| Session API | `https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev` |
| Cognito User Pool | `eu-west-1_q2rAaummA` |
| Cognito Game Client | `2iinqhoja78kj1et6rcv28bjvf` |
| GameLift Fleet | `fleet-848aced2-ac8f-405a-b120-43f4f3904983` |
| FlexMatch Config | `hypermage-vr-dev` |
| S3 Build Bucket | `hypermage-vr-unreal-build-artifacts-dev` |
| Terraform State | S3 `hypermage-vr-terraform-state` / `dev/terraform.tfstate` |
| Terraform Working Dir | `Infra/environments/dev` |
