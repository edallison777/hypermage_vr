# Unreal VR Multiplayer System - System Specification

## Overview

The Unreal VR Multiplayer System is a spec-driven, multi-agent architecture that transforms natural language specifications into fully deployed VR multiplayer experiences for Meta Quest 3 devices. The system operates on a local-first orchestration model with cloud-based infrastructure, supporting 10-15 players per shard with dedicated server architecture.

## Architectural Constraints

### Core Principles

1. **Spec-Driven Development**: All system state changes are captured in versioned specification documents
2. **Local-First Orchestration**: The orchestrator runs locally on developer machines for immediate feedback
3. **Cloud-Based Builds**: Unreal Engine compilation happens on AWS EC2 instances (local UE5.3 installation optional)
4. **Mock-First Testing**: All external systems have mock implementations for local development
5. **Cost-Conscious Design**: Mandatory cost monitoring with automatic budget enforcement

### System Boundaries

- **Target Platform**: Meta Quest 3 with OpenXR API
- **Engine**: Unreal Engine 5.3+
- **Player Capacity**: 10-15 players per shard, maximum 3 concurrent shards
- **Geographic Scope**: EU-West-1 AWS region
- **Session Duration**: Ephemeral sessions with 72-hour TTL for event data
- **Budget Constraint**: £1000 default limit for 72-hour events

## Operating Modes

### Development Mode
- **Orchestrator**: Local execution with SQLite persistence
- **External Systems**: Full mock mode (no AWS API calls)
- **Cost Limits**: Reporting only, no enforcement
- **Approval Gates**: Disabled (autonomous operation)
- **Build System**: Mock builds or local UE5.3 if available

### Staging Mode
- **Orchestrator**: Local execution with real AWS infrastructure
- **External Systems**: Real AWS services with reduced capacity
- **Cost Limits**: Moderate enforcement (£100/day)
- **Approval Gates**: Required for infrastructure changes
- **Build System**: Cloud builds on EC2 with cost tracking

### Production Mode
- **Orchestrator**: Local execution with full AWS infrastructure
- **External Systems**: Full AWS services with complete capacity
- **Cost Limits**: Strict enforcement (£1000/72h default)
- **Approval Gates**: Required for all changes (infrastructure, deployments, budget increases)
- **Build System**: Cloud builds on EC2 with comprehensive cost tracking

## Agent Responsibilities

### Core Orchestration
- **ProducerOrchestratorAgent**: Task decomposition, milestone gating, reward catalog enforcement
- **CostMonitorFinOpsAgent**: Real-time cost tracking, budget enforcement, cost reporting (MANDATORY)

### Content Creation
- **ConversationLevelDesignerAgent**: Natural language to LevelPlan conversion, zone layout generation
- **UnrealLevelBuilderAgent**: LevelPlan to Unreal map conversion, blockout geometry generation
- **AssetPipelineAgent**: Asset import validation, provenance tracking, licensed asset recommendations
- **TechArtVFXAudioAgent**: Tier 1 asset generation, Quest 3 optimization, spatial audio configuration

### Technical Implementation
- **GameplaySystemsAgent**: VR interaction systems, objective implementation, server-side reward emission
- **MultiplayerNetcodeAgent**: Server-authoritative networking, replication strategy, bandwidth management
- **VoiceCommsAgent**: Party voice integration, audio routing, mute/block controls
- **QAAgent**: Test generation, multiplayer validation, VR comfort verification

### Infrastructure & Operations
- **DevOpsAWSAgent**: Terraform orchestration, CI/CD management, observability setup

## Approval and Governance Rules

### Environment-Based Governance

**Development Environment:**
- All operations execute autonomously
- Cost monitoring active but non-blocking
- No approval gates required
- Full mock mode available

**Production Environment:**
- Infrastructure changes require manual approval
- Deployments require manual approval
- Budget increases require manual approval
- All operations logged and audited

### Cost Governance

**Budget Policy Enforcement:**
1. **Warning Threshold**: Alert at 80% of budget limit
2. **Block Threshold**: Prevent operations at 100% of budget limit
3. **Approval Required**: Budget increases must be manually approved
4. **Real-Time Tracking**: All AWS operations tracked with cost attribution

**Cost Optimization:**
- EC2 spot instances for Unreal builds when possible
- Automatic instance termination after build completion
- S3 lifecycle policies (30-day expiration for build artifacts)
- DynamoDB TTL for ephemeral session data (72 hours)

### Asset Governance

**Provenance Requirements:**
- All assets must have complete provenance records
- Origin, license, usage rights must be documented
- Licensed assets require manual approval before use
- No automatic purchases of licensed content

**Asset Tiers:**
- **Tier 0**: Blockout primitives (always allowed)
- **Tier 1**: Generated placeholders from concept art (automatic)
- **Tier 2**: Licensed/marketplace assets (manual approval required)

## Data Persistence Strategy

### Ephemeral Data (72-hour TTL)
- Player session events and interactions
- Gameplay state (positions, inventory, temporary data)
- Build logs and temporary artifacts
- Cost tracking records (after aggregation)

### Persistent Data (No TTL)
- Player reward flags (boolean achievements)
- Asset provenance records
- Specification documents and change history
- Budget policies and cost summaries
- Agent execution plans and results

### Data Storage
- **Local**: SQLite for orchestrator state and execution history
- **Cloud**: DynamoDB for session data, rewards, and events
- **Artifacts**: S3 for build outputs, assets, and documentation

## Security Model

### Authentication & Authorization
- AWS Cognito User Pools for player authentication
- JWT tokens (1-hour expiration, 7-day refresh)
- Server-side validation for all gameplay actions
- Role-based access control (player, moderator, admin)

### Network Security
- TLS 1.3 for all communications
- AWS WAF for DDoS protection
- Rate limiting on all API endpoints
- VPC isolation for GameLift fleets

### Data Protection
- Encryption at rest (DynamoDB, S3)
- No PII in logs or metrics
- GDPR compliance via TTL-based data expiration
- Audit trails for all administrative actions

## Integration Points

### External Systems
- **AWS GameLift**: Server fleet management and matchmaking
- **AWS FlexMatch**: Player matchmaking with custom rules
- **AWS Cognito**: User authentication and JWT token management
- **AWS DynamoDB**: Session data and reward storage
- **AWS Lambda**: Session API endpoints
- **GitHub**: Version control and CI/CD triggers

### MCP Adapters
- **UnrealMCP**: Unreal Engine operations (build, package, deploy)
- **AWSMCP**: AWS service operations (infrastructure, monitoring)
- **GitHubMCP**: Version control operations (commits, PRs, tags)
- **LocalProcessMCP**: Local command execution (testing, validation)

### Communication Protocols
- **Agent-to-Orchestrator**: HTTP/JSON with correlation IDs
- **Orchestrator-to-MCP**: Model Context Protocol over HTTP
- **Client-to-Server**: Unreal networking with GameLift integration
- **Voice Communication**: Unreal Voice Chat Interface with pluggable providers

## Monitoring and Observability

### Key Metrics
- **Performance**: Player count, connection success rate, average latency
- **Cost**: Spend per service, cost per player-hour, budget utilization
- **Quality**: Error rates, agent execution time, build success rate
- **Business**: Session completion rate, reward grant frequency, user engagement

### Alerting Thresholds
- Budget exceeded (80%, 90%, 100% of limit)
- High error rate (>5% over 5 minutes)
- High latency (>200ms average over 5 minutes)
- Authentication failures (>10 per minute)
- Infrastructure health issues

### Logging Strategy
- Structured JSON logs with correlation IDs
- Centralized logging via AWS CloudWatch
- Log retention: 30 days (dev), 90 days (prod)
- No PII in logs for GDPR compliance

## Deployment Architecture

### Local Development
```
Developer Machine
├── Orchestrator (Node.js + SQLite)
├── Agents (TypeScript + Mock MCPs)
├── MCP Adapters (Mock Mode)
└── Test Suite (Unit + Property + Integration)
```

### Cloud Infrastructure
```
AWS EU-West-1
├── GameLift Fleet (Quest 3 servers)
├── FlexMatch (Matchmaking)
├── Cognito (Authentication)
├── DynamoDB (Session data + Rewards)
├── Lambda (Session API)
├── S3 (Build artifacts)
└── EC2 (Unreal build instances)
```

### CI/CD Pipeline
```
GitHub Actions
├── Validate (Lint, Type check, Schema validation)
├── Test (Unit, Property, Integration tests)
├── Build (Unreal artifacts via EC2)
├── Deploy (Terraform apply with approval gates)
└── Monitor (Cost tracking, Health checks)
```

This specification provides the foundational constraints and operating principles for the Unreal VR Multiplayer System, ensuring consistent behavior across all environments while maintaining cost control and quality standards.