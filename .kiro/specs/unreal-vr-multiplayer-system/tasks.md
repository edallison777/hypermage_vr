# Implementation Plan: Unreal VR Multiplayer System

## Overview

This implementation plan breaks down the Unreal VR Multiplayer System into discrete, executable tasks following a vertical slice approach. The vertical slice prioritizes a complete end-to-end flow: natural language specification → LevelPlan → Unreal map → GameLift deployment → multiplayer match → reward summary with TTL expiration.

**Implementation Languages:**
- **TypeScript**: Orchestrator, Agents (via Strands SDK), MCP Adapters, Session API
- **C++**: Unreal Engine gameplay code, VR systems, networking
- **Terraform**: Infrastructure as Code for AWS resources

**Priority:** Complete the vertical slice first to validate all architectural layers before expanding features.

## Tasks

- [x] 1. Repository structure and foundational schemas
  - Create monorepo directory structure (/Specs, /Orchestrator, /Agents, /MCP, /UnrealProject, /Infra, /CI)
  - Create all JSON schema files in /Specs/schemas/
  - Create example JSON files in /Specs/examples/
  - Set up TypeScript project configuration with shared tsconfig
  - Set up package.json with workspace configuration
  - _Requirements: 8.1, 8.2, 9.1, 11.1-11.9_

- [x] 2. Core schema definitions and validation
  - [x] 2.1 Implement LevelPlan.schema.json with zones, spawns, and objectives
    - Define zone types (combat, safe, objective, spawn)
    - Define spatial bounds structure (center, extents)
    - Define player spawn points with position and rotation
    - Define objectives with reward ID references
    - _Requirements: 11.1_
  
  - [x] 2.2 Implement GameplayRules.schema.json with trigger-action patterns
    - Define trigger types and condition structures
    - Define action types and parameter structures
    - Link rules to level IDs
    - _Requirements: 11.2_
  
  - [x] 2.3 Implement AssetSpec.schema.json with provenance tracking
    - Define asset tiers (0: blockout, 1: placeholder, 2: final)
    - Define provenance fields (origin, license, createdBy, cost)
    - Define usage rights structure
    - _Requirements: 11.3, 6.5, 6.6_
  
  - [x] 2.4 Implement BudgetPolicy.schema.json with enforcement rules
    - Define environment types (dev, prod)
    - Define cost limits structure (total, per-service)
    - Define enforcement modes (report, warn, block)
    - _Requirements: 11.7, 7.5, 7.6_
  
  - [x] 2.5 Implement rewards_catalog.json structure
    - Define reward ID format and validation rules
    - Create example rewards (first_objective_complete, session_complete, team_victory)
    - _Requirements: 11.9, 15.1_
  
  - [x] 2.6 Write property test for schema validation
    - **Property 6: Reward Catalog Validation**
    - **Validates: Requirements 5.3, 15.2, 15.3**

- [x] 3. MCP adapter interfaces and mock implementations
  - [x] 3.1 Create MCP adapter base interface
    - Define capability-based request/response protocol
    - Implement mock mode flag and behavior switching
    - Add provenance logging for all operations
    - _Requirements: 12.7_
  
  - [x] 3.2 Implement UnrealMCP adapter with mock
    - Define capabilities: build_project, package_server, generate_level, import_asset
    - Implement cloud build mode using EC2 API (launches instance, executes build, uploads to S3, terminates)
    - Implement local build mode for developers with UE5.3 installed (optional)
    - Implement mock mode with realistic delays and mock artifacts
    - Add cost tracking for EC2 instance usage
    - _Requirements: 12.1, 8a.1-8a.7_
  
  - [x] 3.3 Implement AWSMCP adapter with mock
    - Define capabilities: deploy_gamelift, create_cognito_pool, create_dynamodb_table
    - Implement mock responses simulating AWS operations
    - _Requirements: 12.2_
  
  - [x] 3.4 Implement GitHubMCP adapter with mock
    - Define capabilities: create_pr, commit_changes, create_tag
    - Implement mock responses for version control operations
    - _Requirements: 12.3_
  
  - [x] 3.5 Write property test for MCP mock mode
    - **Property 13: MCP Adapter Mock Mode**
    - **Validates: Requirements 8.5, 12.7**

- [x] 4. Orchestrator core service implementation
  - [x] 4.1 Create Orchestrator HTTP API with Express.js
    - Implement POST /api/v1/plans endpoint
    - Implement POST /api/v1/plans/:planId/execute endpoint
    - Implement GET /api/v1/executions/:executionId endpoint
    - Add structured logging with Winston
    - _Requirements: 19.1, 19.2_
  
  - [x] 4.2 Implement plan generation logic
    - Parse natural language specifications
    - Determine required agents based on specification content
    - Generate execution plan with steps and dependencies
    - Calculate cost estimates using CostModel
    - _Requirements: 19.2_
  
  - [x] 4.3 Implement plan execution engine
    - Execute steps in dependency order
    - Coordinate agent communication via HTTP/JSON
    - Handle agent timeouts and retries
    - Update specification documents with change notes
    - _Requirements: 19.5, 17.1, 17.2_
  
  - [x] 4.4 Implement state persistence with SQLite
    - Store execution plans and status
    - Store agent messages and responses
    - Store cost records and summaries
    - _Requirements: 19.1_
  
  - [x] 4.5 Write property test for plan approval requirement
    - **Property 18: Plan Approval Requirement**
    - **Validates: Requirements 19.4**
  
  - [x] 4.6 Write property test for spec updates
    - **Property 15: Spec Update with Change Notes**
    - **Validates: Requirements 17.1, 17.2**

- [x] 5. Checkpoint - Orchestrator and schemas validated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Agent framework using Strands SDK
  - [x] 6.1 Set up Strands Agent SDK integration
    - Install Strands SDK dependencies
    - Configure AWS AgentCore runtime connection
    - Create base agent class with common functionality
    - _Requirements: 10.1-10.10_
  
  - [x] 6.2 Implement agent communication protocol
    - Define AgentMessage, AgentRequest, AgentResponse interfaces
    - Implement message routing and correlation IDs
    - Add timeout handling and retry logic
    - _Requirements: 19.5_
  
  - [x] 6.3 Implement ProducerOrchestratorAgent
    - Task decomposition and milestone gating
    - Reward catalog enforcement
    - Definitions of done validation
    - _Requirements: 10.1_
  
  - [x] 6.4 Implement ConversationLevelDesignerAgent
    - Natural language to LevelPlan.json conversion
    - Zone layout generation
    - Objective placement logic
    - _Requirements: 10.2_
  
  - [x] 6.5 Write property test for plan generation
    - **Property 17: Orchestrator Plan Generation**
    - **Validates: Requirements 19.2**

- [x] 7. CostMonitorFinOpsAgent implementation (MANDATORY)
  - [x] 7.1 Implement cost tracking for AWS operations
    - Track costs per service (GameLift, Cognito, DynamoDB, Lambda)
    - Store cost records with timestamps and resource IDs
    - _Requirements: 20.2_
  
  - [x] 7.2 Implement budget policy enforcement
    - Load and validate BudgetPolicy.schema.json
    - Check costs against limits before operations
    - Block operations that exceed budget
    - _Requirements: 7.7, 20.4_
  
  - [x] 7.3 Implement cost reporting and warnings
    - Generate cost summaries with breakdowns
    - Issue warnings at threshold percentages
    - Calculate projected costs for 72h events
    - _Requirements: 20.3, 20.5_
  
  - [x] 7.4 Write property test for cost limit enforcement
    - **Property 12: Cost Limit Enforcement**
    - **Validates: Requirements 7.7, 20.4**
  
  - [x] 7.5 Write property test for cost tracking
    - **Property 20: Cost Tracking for AWS Operations**
    - **Validates: Requirements 20.2**

- [x] 8. AssetPipelineAgent and provenance tracking
  - [x] 8.1 Implement asset import validation
    - Validate asset format and metadata
    - Check for required provenance fields
    - Block imports missing provenance
    - _Requirements: 6.5, 6.6_
  
  - [x] 8.2 Implement provenance record management
    - Create provenance records for all assets
    - Track origin, license, cost, usage rights
    - Maintain change history
    - _Requirements: 6.5, 6.6_
  
  - [x] 8.3 Implement licensed asset recommendation system
    - Identify suitable licensed assets
    - Generate recommendations with licensing details
    - Block automatic purchases
    - Wait for manual approval
    - _Requirements: 6.4, 16.1-16.4_
  
  - [x] 8.4 Write property test for provenance completeness
    - **Property 10: Asset Provenance Completeness**
    - **Validates: Requirements 6.5, 6.6**
  
  - [x] 8.5 Write property test for licensed asset handling
    - **Property 9: Licensed Asset Recommendation Without Purchase**
    - **Validates: Requirements 6.4, 16.1-16.4**

- [x] 9. Checkpoint - Core agents and cost monitoring validated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Unreal Engine VR project setup
  - [x] 10.1 Create UE5.3+ project for Meta Quest 3
    - Enable OpenXR plugin
    - Configure Android build settings for Quest 3
    - Set up dedicated server build target
    - **IMPORTANT:** Project structure and configuration files created; actual compilation happens via cloud builds (EC2) or mock mode. Local UE5.3 installation is NOT required to complete this project.
    - _Requirements: 1.1, 1.2, 8a.1-8a.7_
  
  - [x] 10.2 Implement VR Pawn with comfort settings
    - Implement smooth locomotion with speed caps
    - Implement snap turn (default) and smooth turn (optional)
    - Implement comfort vignette on acceleration/rotation
    - Implement teleport fallback
    - Implement optional flight mode with comfort tuning
    - _Requirements: 1.3-1.7_
  
  - [x] 10.3 Implement dedicated server architecture
    - Set up server-authoritative game mode
    - Implement client-server replication
    - Add server-side validation for all gameplay actions
    - _Requirements: 2.1_
  
  - [x] 10.4 Implement player capacity management
    - Enforce 10-15 player limit per shard
    - Reject connections beyond capacity
    - _Requirements: 2.2_
  
  - [x] 10.5 Write property test for server authority
    - **Property 1: Server Authority for Gameplay State**
    - **Validates: Requirements 2.1**
  
  - [x] 10.6 Write property test for shard capacity
    - **Property 2: Shard Player Capacity Enforcement**
    - **Validates: Requirements 2.2**

- [x] 11. GameLift integration and authentication
  - [x] 11.1 Implement GameLift SDK integration
    - Initialize GameLift server SDK
    - Implement player session validation
    - Handle server health reporting
    - _Requirements: 2.4_
  
  - [x] 11.2 Implement JWT authentication
    - Integrate Cognito JWT validation
    - Validate token signature and expiration
    - Extract player ID from token claims
    - Reject invalid or expired tokens
    - _Requirements: 3.1-3.4_
  
  - [x] 11.3 Write property test for JWT validation
    - **Property 3: JWT Token Validation**
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [x] 12. Voice communication system
  - [x] 12.1 Implement Unreal Voice Chat Interface integration
    - Set up party voice channel
    - Route audio to all players in shard
    - Implement pluggable provider interface
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 12.2 Implement mock voice provider
    - Simulate voice connections
    - Provide no-op audio routing for testing
    - _Requirements: 4.4_
  
  - [x] 12.3 Write property test for party voice routing
    - **Property 4: Party Voice Routing**
    - **Validates: Requirements 4.2, 4.5**

- [x] 13. Session management and reward system
  - [x] 13.1 Implement ephemeral session logic
    - Create session on match start (state: CREATED → ACTIVE)
    - Track player events during session
    - Transition to ENDED state on session completion/timeout/disconnect
    - Discard gameplay state on session end
    - Set TTL to 72 hours after session end
    - _Requirements: 5.1, 5.5, 5.6, 5.7_
  
  - [x] 13.2 Implement reward granting system
    - Load and validate rewards_catalog.json
    - Validate reward IDs against catalog before granting
    - Store rewards as boolean flags in PlayerRewards table
    - Reject invalid reward IDs with error code INVALID_REWARD_ID
    - Handle catalog loading errors with error code REWARD_CATALOG_NOT_FOUND
    - _Requirements: 5.2, 5.3, 15.1, 15.2, 15.3, 15.5_
  
  - [x] 13.3 Implement PlayerSessionSummary generation
    - Collect granted rewards at session end
    - Generate summary with player ID, session ID, and reward list
    - Create stub interface for Session API (actual API implemented in Task 15.4)
    - Store summary locally or send to mock Session API endpoint
    - _Requirements: 5.2_
  
  - [x] 13.4 Write property test for session ephemeral state
    - **Property 5: Session Ephemeral State**
    - **Validates: Requirements 5.1, 5.2, 5.5, 5.6, 5.7**
    - Test that only rewards persist after session ends
    - Test that gameplay state (positions, events, inventory) is discarded
    - Test TTL is set to 72 hours after session end
    - Test session state transitions: CREATED → ACTIVE → ENDED → EXPIRED
  
  - [x] 13.5 Write property test for reward storage format
    - **Property 14: Reward Storage Format**
    - **Validates: Requirements 15.4, 15.5**
    - Test rewards stored as boolean flags with string identifiers
    - Test reward records have no TTL attribute (persistent)
    - Test invalid reward IDs return INVALID_REWARD_ID error
    - Test catalog loading failures return REWARD_CATALOG_NOT_FOUND error

- [x] 14. Checkpoint - Unreal project core systems validated
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. AWS infrastructure with Terraform
  - [x] 15.0 Create Unreal Build EC2 infrastructure
    - Create Terraform module for EC2 build instances (g4dn.xlarge)
    - Create pre-configured AMI with UE5.3, Android SDK, GameLift SDK
    - Set up S3 bucket for build artifacts with lifecycle policies
    - Configure IAM roles for EC2 build instances
    - Implement spot instance support for cost optimization
    - _Requirements: 8a.1-8a.7_
  
  - [x] 15.1 Create GameLift fleet Terraform module
    - Define fleet configuration with Quest 3 server builds
    - Configure scaling policies (max 3 shards initially)
    - Set up fleet locations in eu-west-1
    - _Requirements: 2.4, 2.5, 2.6_
  
  - [x] 15.2 Create FlexMatch Terraform module
    - Define matchmaking configuration
    - Set up rule sets for 10-15 player matches
    - Configure matchmaking queues
    - _Requirements: 2.5, 2.6_
  
  - [x] 15.3 Create Cognito User Pools Terraform module
    - Define user pool with JWT configuration
    - Set up app clients for game authentication
    - Configure token expiration (1h access, 7d refresh)
    - _Requirements: 3.1, 3.2_
  
  - [x] 15.4 Create Session API Terraform module
    - Define API Gateway with Cognito authorizer
    - Create Lambda functions for endpoints
    - Implement POST /matchmaking/start
    - Implement GET /matchmaking/status/{ticketId}
    - Implement POST /session-summary
    - _Requirements: 13.4_
  
  - [x] 15.5 Create DynamoDB tables Terraform module
    - Create PlayerSessions table with TTL
    - Create InteractionEvents table with TTL
    - Create PlayerRewards table (no TTL)
    - Configure TTL attribute on expires_at_epoch field
    - _Requirements: 13.5_
  
  - [x] 15.6 Write property test for event TTL assignment
    - **Property 7: Event TTL Assignment**
    - **Validates: Requirements 5.4**

- [ ] 16. Environment-based governance and approval gates
  - [x] 16.1 Implement environment detection
    - Detect dev vs prod environment from configuration
    - Load appropriate BudgetPolicy for environment
    - _Requirements: 7.1-7.4_
  
  - [x] 16.2 Implement approval gate system
    - Block infrastructure changes in prod until approved
    - Block deployments in prod until approved
    - Block budget increases in prod until approved
    - Allow autonomous operation in dev with reporting
    - _Requirements: 7.1-7.4_
  
  - [x] 16.3 Write property test for approval gates
    - **Property 11: Environment-Based Approval Gates**
    - **Validates: Requirements 7.1-7.4**

- [ ] 17. Remaining specialized agents
  - [x] 17.1 Implement UnrealLevelBuilderAgent
    - LevelPlan to Unreal map conversion
    - Blockout geometry generation
    - Gameplay pass implementation
    - _Requirements: 10.3_
  
  - [x] 17.2 Implement GameplaySystemsAgent
    - VR interaction implementation
    - Objective system implementation
    - Server-side reward emission
    - _Requirements: 10.4_
  
  - [x] 17.3 Implement MultiplayerNetcodeAgent
    - Replication strategy implementation
    - Bandwidth budget management
    - Join/leave handling
    - _Requirements: 10.5_
  
  - [x] 17.4 Implement VoiceCommsAgent
    - Party voice integration
    - Mute/block controls
    - _Requirements: 10.6_
  
  - [x] 17.5 Implement TechArtVFXAudioAgent
    - Tier 1 asset generation from 2D concept art
    - Niagara VFX setup
    - Spatial audio configuration
    - Quest 3 performance optimization
    - _Requirements: 10.7, 6.3_
  
  - [x] 17.6 Implement QAAgent
    - Unit test generation
    - Integration test generation
    - Multiplayer soak test support
    - _Requirements: 10.8_
  
  - [x] 17.7 Implement DevOpsAWSAgent
    - Terraform plan/apply orchestration
    - CI/CD pipeline management
    - Observability setup
    - _Requirements: 10.9_
  
  - [x] 17.8 Write property test for Tier 1 asset generation
    - **Property 8: Tier 1 Asset Generation**
    - **Validates: Requirements 6.3**

- [ ] 18. Checkpoint - All agents implemented
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 19. CI/CD workflows with GitHub Actions
  - [x] 19.1 Create validate_specs workflow
    - Run JSON schema validation
    - Run unit tests
    - Run linting and type checking
    - _Requirements: 14.1_
  
  - [x] 19.2 Create build_unreal workflow
    - Build dedicated server artifact
    - Package for Quest 3
    - Upload artifacts to S3
    - _Requirements: 14.2_
  
  - [x] 19.3 Create terraform_plan workflow
    - Run terraform plan
    - Post cost estimates via CostMonitor
    - Comment on PR with changes
    - _Requirements: 14.3_
  
  - [x] 19.4 Create terraform_apply_dev workflow
    - Apply changes to dev environment
    - Gated by approval
    - _Requirements: 14.4_
  
  - [x] 19.5 Create release_prod workflow
    - Require manual approval
    - Enforce budget check
    - Deploy to production
    - _Requirements: 14.5_

- [ ] 20. Vertical slice integration and testing
  - [x] 20.1 Implement end-to-end vertical slice test
    - Test: Natural language → LevelPlan conversion
    - Test: LevelPlan → Unreal map generation
    - Test: GameLift deployment and matchmaking
    - Test: Multiplayer session with reward granting
    - Test: PlayerSessionSummary with TTL expiration
    - _Requirements: 18.1-18.6_
  
  - [x] 20.2 Create example level from LevelPlan.example.json
    - Generate Unreal map with blockout geometry
    - Place player spawns
    - Implement objectives with reward triggers
    - _Requirements: 18.3_
  
  - [x] 20.3 Write property test for multi-agent coordination
    - **Property 19: Multi-Agent Coordination**
    - **Validates: Requirements 19.5**
  
  - [x] 20.4 Write integration tests for vertical slice
    - Test complete flow in mock mode
    - Validate all specification documents generated
    - Verify cost tracking throughout

- [x] 21. Documentation and getting started guide
  - [x] 21.1 Write SPEC.md system overview
    - Document architectural constraints
    - Document operating modes (dev vs prod)
    - Document agent responsibilities
    - Document approval and governance rules
    - _Requirements: 9.1_
  
  - [x] 21.2 Write ACCEPTANCE_TESTS.md
    - Document vertical slice test scenarios
    - Document expected outcomes
    - Document validation criteria
    - _Requirements: 9.1_
  
  - [x] 21.3 Write Getting Started guide
    - Local development setup with mocks
    - Running the orchestrator
    - Generating a sample level
    - Running local multiplayer test
    - Deploying to AWS dev environment
  
  - [x] 21.4 Create README.md files for each component
    - /Orchestrator/README.md
    - /Agents/README.md
    - /MCP/README.md
    - /UnrealProject/README.md
    - /Infra/README.md

- [x] 22. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify vertical slice works end-to-end
  - Verify cost monitoring and budget enforcement
  - Verify all documentation is complete

## Notes

- All tasks are required for comprehensive validation from the start
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The vertical slice (tasks 20.1-20.2) is the highest priority for validating the complete architecture
- All agents must be built using Strands Agent SDK and deployed to AWS AgentCore runtime
- TypeScript is used for Orchestrator, Agents, and MCP adapters; C++ for Unreal Engine code
