# Hypermage VR

A spec-driven, multi-agent system that designs, implements, and deploys Unreal Engine VR multiplayer levels from natural-language specifications.

## Overview

Hypermage VR is a production-oriented system that transforms conversational level design into fully deployed VR multiplayer experiences. The system targets Meta Quest 3 devices, supports 10-15 players per shard with dedicated server architecture, and enforces strict cost governance while maintaining full provenance tracking for all assets.

### Key Features

- **Conversational Level Design**: Natural language → structured LevelPlan → Unreal Engine map
- **Multi-Agent Architecture**: 11 specialized agents built with Strands SDK, deployed to AWS AgentCore
- **VR-First**: Meta Quest 3 with OpenXR, comprehensive comfort settings (snap turn, vignette, teleport)
- **Dedicated Server Architecture**: GameLift + FlexMatch for authoritative multiplayer
- **Cost Governance**: Mandatory £1000/72h budget enforcement with CostMonitorFinOpsAgent
- **Asset Provenance**: Full tracking of origin, licensing, and usage rights
- **Spec-Driven Development**: All state changes captured in versioned specification documents

## Architecture

The system consists of three primary layers:

1. **Orchestration Layer**: Local-first orchestrator managing plan→execute workflow
2. **Agent Layer**: 11 specialized agents (LevelDesigner, UnrealBuilder, Gameplay, Netcode, Voice, TechArt, AssetPipeline, QA, DevOps, CostMonitor)
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

- Node.js 18+
- TypeScript 5+
- Unreal Engine 5.3+
- Terraform 1.5+
- AWS CLI configured
- Meta Quest 3 device (for testing)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/hypermage_vr.git
   cd hypermage_vr
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up local development with mocks**
   ```bash
   npm run setup:local
   ```

4. **Start the orchestrator**
   ```bash
   npm run orchestrator:start
   ```

5. **Generate a sample level**
   ```bash
   npm run example:generate-level
   ```

See the [Getting Started Guide](./Specs/GETTING_STARTED.md) for detailed instructions.

## Documentation

- [System Specification](./Specs/SPEC.md) - Architectural constraints, operating modes, agent responsibilities
- [Requirements](./kiro/specs/unreal-vr-multiplayer-system/requirements.md) - 20 detailed requirements with acceptance criteria
- [Design Document](./kiro/specs/unreal-vr-multiplayer-system/design.md) - Complete architecture with 22 correctness properties
- [Implementation Tasks](./kiro/specs/unreal-vr-multiplayer-system/tasks.md) - 22 major tasks with 100+ sub-tasks
- [Acceptance Tests](./Specs/ACCEPTANCE_TESTS.md) - End-to-end test scenarios

## Development Workflow

1. **Plan Phase**: Orchestrator generates execution plan from natural language
2. **Review Phase**: Human designer reviews and approves plan
3. **Execute Phase**: Agents execute plan steps in dependency order
4. **Validation Phase**: Property-based tests validate correctness properties

## Technology Stack

- **Languages**: TypeScript (Orchestrator, Agents, MCP), C++ (Unreal Engine)
- **Agent Framework**: Strands Agent SDK + AWS AgentCore
- **VR Platform**: Unreal Engine 5+ with OpenXR for Meta Quest 3
- **Cloud Infrastructure**: AWS (GameLift, FlexMatch, Cognito, DynamoDB, Lambda)
- **IaC**: Terraform
- **CI/CD**: GitHub Actions
- **Testing**: Jest (unit), fast-check (property-based), RapidCheck (C++)

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

🚧 **In Development** - Currently implementing the vertical slice (natural language → LevelPlan → Unreal map → GameLift match → gameplay → reward summary with TTL)

---

Built with ❤️ for VR multiplayer level design
