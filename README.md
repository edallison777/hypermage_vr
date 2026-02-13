# Unreal VR Multiplayer System

A spec-driven, multi-agent system that designs, implements, and deploys Unreal Engine VR multiplayer levels from natural-language specifications.

## Overview

The Unreal VR Multiplayer System is a production-oriented platform that transforms conversational level design into fully deployed VR multiplayer experiences. The system targets Meta Quest 3 devices, supports 10-15 players per shard with dedicated server architecture, and enforces strict cost governance while maintaining full provenance tracking for all assets.

### Key Features

- **Conversational Level Design**: Natural language → structured LevelPlan → Unreal Engine map
- **Multi-Agent Architecture**: 10 specialized agents coordinated by local orchestrator
- **Cloud-Based Builds**: Unreal Engine compilation on AWS EC2 (no local UE5.3 required)
- **VR-First**: Meta Quest 3 with OpenXR, comprehensive comfort settings (snap turn, vignette, teleport)
- **Dedicated Server Architecture**: GameLift + FlexMatch for authoritative multiplayer
- **Cost Governance**: Mandatory £1000/72h budget enforcement with CostMonitorFinOpsAgent
- **Asset Provenance**: Full tracking of origin, licensing, and usage rights
- **Spec-Driven Development**: All state changes captured in versioned specification documents
- **Mock-First Testing**: Complete local development without external dependencies

## Architecture

The system consists of three primary layers:

1. **Orchestration Layer**: Local-first orchestrator managing plan→execute workflow
2. **Agent Layer**: 10 specialized agents (LevelDesigner, UnrealBuilder, Gameplay, Netcode, Voice, TechArt, AssetPipeline, QA, DevOps, CostMonitor)
3. **Infrastructure Layer**: AWS services (GameLift, FlexMatch, Cognito, DynamoDB) with full mock support

## Repository Structure

```
/Specs              # System documentation, schemas, examples, acceptance tests
/Orchestrator       # Local-first orchestration service
/Agents             # Specialized agent implementations (Strands SDK)
/MCP                # Model Context Protocol adapters with mocks
/UnrealProject      # UE5+ Quest 3 VR project
/Infra              # Terraform modules for AWS infrastructure
/CI                 # GitHub Actions workflows
```

## Getting Started

### Prerequisites

- Node.js 20+
- TypeScript 5+
- AWS CLI configured (for staging/prod)
- Terraform 1.5+ (for infrastructure deployment)
- Meta Quest 3 device (for testing)
- **Optional**: Unreal Engine 5.3+ (for local build optimization)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd unreal-vr-multiplayer-system
   ```

2. **Install dependencies**
   ```bash
   npm install
   npm run install:all
   ```

3. **Start the orchestrator in mock mode**
   ```bash
   cd Orchestrator
   npm run dev:mock
   ```

4. **Generate a sample level**
   ```bash
   curl -X POST http://localhost:3000/api/v1/plans \
     -H "Content-Type: application/json" \
     -d '{"specification": "Create a VR arena with combat and safe zones", "context": {"targetEnvironment": "dev"}}'
   ```

See the [Getting Started Guide](./GETTING_STARTED.md) for detailed instructions.

## Documentation

- [System Specification](./SPEC.md) - Architectural constraints, operating modes, agent responsibilities
- [Getting Started Guide](./GETTING_STARTED.md) - Local development setup and workflow
- [Acceptance Tests](./ACCEPTANCE_TESTS.md) - End-to-end test scenarios and validation criteria
- [Requirements](./.kiro/specs/unreal-vr-multiplayer-system/requirements.md) - 20 detailed requirements with acceptance criteria
- [Design Document](./.kiro/specs/unreal-vr-multiplayer-system/design.md) - Complete architecture with 22 correctness properties
- [Implementation Tasks](./.kiro/specs/unreal-vr-multiplayer-system/tasks.md) - 22 major tasks with 100+ sub-tasks

## Development Workflow

1. **Plan Phase**: Orchestrator generates execution plan from natural language
2. **Review Phase**: Human designer reviews and approves plan
3. **Execute Phase**: Agents execute plan steps in dependency order
4. **Validation Phase**: Property-based tests validate correctness properties

## Technology Stack

- **Languages**: TypeScript (Orchestrator, Agents, MCP), C++ (Unreal Engine)
- **Runtime**: Node.js 20+ for all TypeScript components
- **VR Platform**: Unreal Engine 5.3+ with OpenXR for Meta Quest 3
- **Build System**: Cloud-based builds on AWS EC2 g4dn instances (local UE5.3 optional)
- **Cloud Infrastructure**: AWS (GameLift, FlexMatch, Cognito, DynamoDB, Lambda)
- **IaC**: Terraform for infrastructure as code
- **CI/CD**: GitHub Actions
- **Testing**: Jest (unit), fast-check (property-based), integration tests

## Cost Governance

The system enforces strict cost limits:
- **Default Budget**: £1000 for 72-hour events
- **Dev Environment**: Autonomous execution with cost reporting
- **Prod Environment**: Approval gates for infrastructure changes, deployments, and budget increases
- **CostMonitorFinOpsAgent**: Mandatory component tracking all AWS costs in real-time

## Contributing

This is a production-oriented system designed for clarity, constraints, and traceability. See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

[Add your license here]

## Status

✅ **Core Implementation Complete** - Vertical slice implemented and tested
- Natural language → LevelPlan conversion
- LevelPlan → Unreal map generation  
- GameLift deployment and matchmaking
- Multiplayer session with reward granting
- PlayerSessionSummary with TTL expiration
- Cost monitoring and budget enforcement
- Asset provenance tracking
- Property-based testing (22 core properties)

🚧 **In Progress** - Documentation and final validation

---

Built with ❤️ for VR multiplayer level design
