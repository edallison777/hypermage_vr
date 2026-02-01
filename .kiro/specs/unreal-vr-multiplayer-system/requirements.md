# Requirements Document: Unreal VR Multiplayer System

## Introduction

The Unreal VR Multiplayer System is a spec-driven, multi-agent system that designs, implements, and deploys Unreal Engine VR multiplayer levels from natural-language specifications. The system targets Meta Quest 3 devices, supports 10-15 players per shard with dedicated server architecture, integrates AWS services for authentication and matchmaking, and enforces strict cost governance while maintaining full provenance tracking for all assets.

## Glossary

- **System**: The complete Unreal VR Multiplayer System including all agents, orchestrator, and infrastructure
- **Orchestrator**: The local-first orchestration service that manages the plan→execute workflow
- **Agent**: A specialized AI component responsible for a specific domain (e.g., LevelDesigner, UnrealBuilder)
- **MCP_Adapter**: Model Context Protocol adapter providing capability-based interfaces to external systems
- **Shard**: A single multiplayer game instance supporting 10-15 players
- **Level_Plan**: A structured specification document describing a VR multiplayer level
- **Reward_ID**: A string identifier for a boolean reward flag stored in the rewards catalog
- **Provenance_Record**: A tracking record documenting the origin and licensing of an asset
- **Budget_Policy**: A configuration document defining cost limits and enforcement rules
- **Comfort_Setting**: VR configuration options designed to reduce motion sickness
- **Mock_Mode**: A testing mode where external system calls are simulated locally
- **TTL**: Time-To-Live - An expiration timestamp for ephemeral data records. After the TTL expires, DynamoDB automatically deletes the record. For this system, session data has a 72-hour TTL after session end, giving you 72 hours to query or process session information before it's automatically deleted.
- **Vertical_Slice**: A complete end-to-end feature implementation demonstrating all system layers

## Requirements

### Requirement 1: VR Platform Support

**User Story:** As a VR developer, I want to target Meta Quest 3 devices with proper VR comfort settings, so that players have a comfortable and accessible experience.

#### Acceptance Criteria

1. THE System SHALL target Meta Quest 3 devices using OpenXR API
2. THE System SHALL use Unreal Engine 5 or later as the rendering platform
3. THE System SHALL enable smooth locomotion as the default movement mode
4. THE System SHALL enable snap turn as the default rotation mode
5. THE System SHALL enable comfort vignette by default to reduce motion sickness
6. THE System SHALL provide teleport locomotion as a fallback option
7. WHERE flight mode is enabled, THE System SHALL provide comfort tuning parameters

### Requirement 2: Multiplayer Architecture

**User Story:** As a game architect, I want a dedicated server authoritative architecture with proper player capacity, so that the game is secure and scalable.

#### Acceptance Criteria

1. THE System SHALL use dedicated server authoritative architecture for all gameplay
2. THE System SHALL support 10-15 players per shard
3. THE System SHALL support a maximum of 3 concurrent shards initially
4. THE System SHALL use Amazon GameLift for server fleet management
5. THE System SHALL use Amazon FlexMatch for matchmaking
6. THE System SHALL deploy all infrastructure to the eu-west-1 AWS region

### Requirement 3: Authentication System

**User Story:** As a security engineer, I want JWT-based authentication using AWS Cognito, so that player identities are securely managed.

#### Acceptance Criteria

1. THE System SHALL use Amazon Cognito User Pools for player authentication
2. THE System SHALL use JWT tokens for session authentication
3. WHEN a player connects to a game server, THE System SHALL validate the JWT token
4. WHEN a JWT token is invalid or expired, THE System SHALL reject the connection

### Requirement 4: Voice Communication

**User Story:** As a player, I want party voice chat with all players in my shard, so that I can communicate during gameplay.

#### Acceptance Criteria

1. THE System SHALL provide party voice communication within each shard
2. WHEN a player is in a shard, THE System SHALL allow them to hear all other players in that shard
3. THE System SHALL use a pluggable voice provider interface
4. THE System SHALL support mock voice provider for testing
5. THE System SHALL NOT support spatial audio or proximity-based voice

### Requirement 5: Session Management

**User Story:** As a system architect, I want ephemeral sessions with reward-only persistence, so that we minimize data storage costs while tracking player achievements.

#### Acceptance Criteria

1. THE System SHALL create ephemeral sessions that do not persist gameplay state
2. THE System SHALL persist only reward data as boolean flags
3. THE System SHALL store reward flags using string identifiers from the rewards catalog
4. THE System SHALL store event data with automatic TTL expiration set to 72 hours after session end
5. WHEN a session ends, THE System SHALL discard all non-reward gameplay state
6. THE System SHALL define session states: CREATED, ACTIVE, ENDED, EXPIRED
7. THE System SHALL transition sessions through states: CREATED → ACTIVE (on match start) → ENDED (on match completion/timeout/disconnect) → EXPIRED (after TTL)

### Requirement 6: Asset Management

**User Story:** As a content creator, I want hand-crafted levels with agent assistance and proper asset provenance, so that I maintain creative control while ensuring legal compliance.

#### Acceptance Criteria

1. THE System SHALL support hand-crafted level creation with agent assistance
2. THE System SHALL support Tier 0 assets using blockout primitives
3. THE System SHALL support Tier 1 assets by auto-generating placeholders from 2D concept art
4. WHEN licensed assets are identified, THE System SHALL recommend them without auto-purchasing
5. THE System SHALL track full provenance for all assets
6. THE System SHALL record asset origin, licensing terms, and usage rights in provenance records

### Requirement 7: Cost Governance

**User Story:** As a project manager, I want automated cost enforcement with different rules for dev and prod, so that we stay within budget while allowing development flexibility.

#### Acceptance Criteria

1. WHEN in development environment, THE System SHALL operate autonomously with cost reporting
2. WHEN in production environment, THE System SHALL require approval gates for infrastructure changes
3. WHEN in production environment, THE System SHALL require approval gates for deployments
4. WHEN in production environment, THE System SHALL require approval gates for budget increases
5. THE System SHALL enforce a default budget of £1000 or less for a 72-hour event
6. THE System SHALL allow budget limits to be adjusted through budget policy configuration
7. THE System SHALL automatically enforce cost limits through the CostMonitorFinOpsAgent

### Requirement 8: Infrastructure Organization

**User Story:** As a DevOps engineer, I want a monorepo structure with proper CI/CD and infrastructure as code, so that the system is maintainable and deployable.

#### Acceptance Criteria

1. THE System SHALL organize all code in a monorepo structure
2. THE System SHALL use GitHub for version control
3. THE System SHALL use GitHub Actions for CI/CD pipelines
4. THE System SHALL use Terraform for infrastructure as code
5. THE System SHALL support full mock mode for all external systems
6. THE System SHALL use cloud-based EC2 instances for Unreal Engine builds
7. THE System SHALL NOT require local Unreal Engine installation for orchestrator or agent operation

### Requirement 8a: Cloud-Based Unreal Build System

**User Story:** As a developer, I want Unreal Engine builds to happen in the cloud, so that I don't need to install UE5.3 locally and can work from any machine.

**IMPORTANT:** This requirement ensures the project can be completed WITHOUT local UE5.3 installation. All Unreal Engine compilation happens on AWS EC2 instances, making the system accessible from any development machine.

#### Acceptance Criteria

1. THE System SHALL use AWS EC2 g4dn instances for Unreal Engine compilation and packaging
2. THE UnrealMCP adapter SHALL orchestrate remote builds via EC2 API
3. THE System SHALL provide pre-configured AMIs with UE5.3, Android SDK, and GameLift SDK
4. THE System SHALL support mock mode for UnrealMCP that simulates builds without EC2
5. THE System SHALL upload build artifacts to S3 for distribution
6. THE System SHALL support local UE5.3 installation as an optional optimization for developers who have it
7. THE System SHALL terminate EC2 instances after build completion to minimize costs

**Note:** Local UE5.3 installation is OPTIONAL for performance optimization only. The system is fully functional using cloud builds alone.

### Requirement 9: System Architecture

**User Story:** As a system architect, I want a well-organized deliverable structure with clear separation of concerns, so that the system is maintainable and extensible.

#### Acceptance Criteria

1. THE System SHALL include a /Specs directory containing system documentation, schemas, examples, and acceptance tests
2. THE System SHALL include an /Orchestrator directory containing the local-first orchestration service
3. THE System SHALL include an /Agents directory containing all specialized agent implementations
4. THE System SHALL include an /MCP directory containing capability-based MCP adapters with mocks
5. THE System SHALL include a /UnrealProject directory containing the UE5+ Quest 3 VR project
6. THE System SHALL include an /Infra directory containing Terraform modules
7. THE System SHALL include a /CI directory containing GitHub Actions workflows

### Requirement 10: Specialized Agents

**User Story:** As a system architect, I want specialized agents for different domains, so that each aspect of development is handled by an expert component.

#### Acceptance Criteria

1. THE System SHALL include a LevelDesigner agent for level design tasks
2. THE System SHALL include an UnrealBuilder agent for Unreal Engine build tasks
3. THE System SHALL include a Gameplay agent for gameplay logic implementation
4. THE System SHALL include a Netcode agent for networking implementation
5. THE System SHALL include a Voice agent for voice communication integration
6. THE System SHALL include a TechArt agent for technical art tasks
7. THE System SHALL include an AssetPipeline agent for asset processing
8. THE System SHALL include a QA agent for quality assurance testing
9. THE System SHALL include a DevOps agent for deployment and infrastructure
10. THE System SHALL include a CostMonitorFinOpsAgent for cost monitoring and enforcement

### Requirement 11: Schema Definitions

**User Story:** As a developer, I want well-defined JSON schemas for all data structures, so that data validation and integration are consistent.

#### Acceptance Criteria

1. THE System SHALL define a LevelPlan.schema.json for level specifications
2. THE System SHALL define a GameplayRules.schema.json for gameplay rule definitions
3. THE System SHALL define an AssetSpec.schema.json for asset specifications
4. THE System SHALL define a DeploySpec.schema.json for deployment configurations
5. THE System SHALL define an InteractionEvent.schema.json for player interaction events
6. THE System SHALL define a PlayerSessionSummary.schema.json for session summaries
7. THE System SHALL define a BudgetPolicy.schema.json for cost governance policies
8. THE System SHALL define a CostModel.schema.json for cost calculation models
9. THE System SHALL define a rewards_catalog.json for valid reward identifiers

### Requirement 12: MCP Adapter Capabilities

**User Story:** As a system integrator, I want MCP adapters for all external systems with mock support, so that development and testing can proceed without external dependencies.

#### Acceptance Criteria

1. THE System SHALL provide an Unreal MCP adapter for Unreal Engine operations
2. THE System SHALL provide an AWS MCP adapter for AWS service operations
3. THE System SHALL provide a GitHub MCP adapter for version control operations
4. THE System SHALL provide a LocalProcess MCP adapter for local command execution
5. THE System SHALL provide an ImageGen MCP adapter for image generation
6. THE System SHALL provide an AudioGen MCP adapter for audio generation
7. WHEN mock mode is enabled, THE System SHALL simulate all MCP adapter operations locally

### Requirement 13: AWS Infrastructure Components

**User Story:** As a cloud architect, I want Terraform modules for all AWS infrastructure, so that infrastructure is reproducible and version-controlled.

#### Acceptance Criteria

1. THE System SHALL provide a Terraform module for Amazon GameLift fleet configuration
2. THE System SHALL provide a Terraform module for Amazon FlexMatch matchmaking configuration
3. THE System SHALL provide a Terraform module for Amazon Cognito User Pools
4. THE System SHALL provide a Terraform module for Session API implementation
5. THE System SHALL provide a Terraform module for DynamoDB tables with TTL configuration
6. THE System SHALL provide a Terraform module for observability and monitoring

### Requirement 14: CI/CD Workflows

**User Story:** As a DevOps engineer, I want automated CI/CD workflows for validation, building, and deployment, so that releases are consistent and reliable.

#### Acceptance Criteria

1. THE System SHALL provide a GitHub Actions workflow for validation
2. THE System SHALL provide a GitHub Actions workflow for building artifacts
3. THE System SHALL provide a GitHub Actions workflow for Terraform plan operations
4. THE System SHALL provide a GitHub Actions workflow for Terraform apply operations
5. THE System SHALL provide a GitHub Actions workflow for release management

### Requirement 15: Reward System

**User Story:** As a game designer, I want a reward catalog system with validation, so that only approved rewards can be granted to players.

#### Acceptance Criteria

1. THE System SHALL maintain a rewards_catalog.json file containing all valid reward identifiers
2. WHEN a reward is granted, THE System SHALL validate the reward ID against the rewards catalog
3. WHEN a reward ID is not in the catalog, THE System SHALL reject the reward grant operation with error code INVALID_REWARD_ID
4. THE System SHALL store granted rewards as boolean flags with string identifiers
5. WHEN the rewards catalog cannot be loaded, THE System SHALL reject reward operations with error code REWARD_CATALOG_NOT_FOUND

### Requirement 16: Licensed Asset Handling

**User Story:** As a legal compliance officer, I want licensed assets to be recommended only without automatic purchase, so that we maintain control over licensing agreements.

#### Acceptance Criteria

1. WHEN a licensed asset is identified as suitable, THE System SHALL recommend the asset
2. THE System SHALL NOT automatically purchase licensed assets
3. THE System SHALL provide asset details including licensing terms in recommendations
4. THE System SHALL wait for manual approval before using licensed assets

### Requirement 17: Spec-Driven State Management

**User Story:** As a system architect, I want all state changes to update specification documents with change notes, so that the system maintains a clear audit trail.

#### Acceptance Criteria

1. WHEN any system state changes, THE System SHALL update the relevant specification document
2. WHEN updating a specification, THE System SHALL include change notes documenting the modification
3. THE System SHALL maintain version history for all specification documents

### Requirement 18: Vertical Slice Priority

**User Story:** As a project manager, I want a complete vertical slice implementation first, so that we validate the entire system architecture early.

#### Acceptance Criteria

1. THE System SHALL prioritize implementing a single complete vertical slice
2. THE Vertical_Slice SHALL include natural language input to LevelPlan conversion
3. THE Vertical_Slice SHALL include LevelPlan to Unreal Engine map generation
4. THE Vertical_Slice SHALL include GameLift matchmaking and server connection
5. THE Vertical_Slice SHALL include gameplay session execution
6. THE Vertical_Slice SHALL include reward summary generation with TTL expiration

### Requirement 19: Orchestrator Workflow

**User Story:** As a system user, I want a local-first orchestrator with plan→execute workflow, so that I can review plans before execution.

#### Acceptance Criteria

1. THE Orchestrator SHALL run locally on the developer's machine
2. THE Orchestrator SHALL implement a plan phase that generates execution plans
3. THE Orchestrator SHALL implement an execute phase that carries out approved plans
4. WHEN a plan is generated, THE Orchestrator SHALL present it for review before execution
5. THE Orchestrator SHALL coordinate multiple agents to complete complex tasks

### Requirement 20: Cost Monitoring Enforcement

**User Story:** As a financial controller, I want mandatory cost monitoring with automatic enforcement, so that budget overruns are prevented.

#### Acceptance Criteria

1. THE System SHALL include the CostMonitorFinOpsAgent as a mandatory component
2. THE CostMonitorFinOpsAgent SHALL monitor all AWS resource costs in real-time
3. WHEN costs approach budget limits, THE CostMonitorFinOpsAgent SHALL issue warnings
4. WHEN costs exceed budget limits, THE CostMonitorFinOpsAgent SHALL prevent further resource provisioning
5. THE CostMonitorFinOpsAgent SHALL generate cost reports for all operations
