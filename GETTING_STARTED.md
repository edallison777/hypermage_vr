# Getting Started - Unreal VR Multiplayer System

## Overview

This guide walks you through setting up and running the Unreal VR Multiplayer System locally. The system is designed to work without requiring local Unreal Engine installation - all builds happen in the cloud on AWS EC2 instances.

## Prerequisites

### Required Software
- **Node.js 20+** - For orchestrator and agents
- **Git** - For version control
- **AWS CLI** - For cloud infrastructure (staging/prod only)
- **Terraform 1.5+** - For infrastructure deployment (staging/prod only)

### Optional Software
- **Unreal Engine 5.3+** - For local builds (performance optimization only)
- **Meta Quest Developer Hub** - For Quest 3 testing
- **Docker** - For containerized development (optional)

### AWS Account Setup (For Staging/Production)
1. Create AWS account with appropriate permissions
2. Configure AWS CLI with credentials
3. Ensure access to required services:
   - GameLift, FlexMatch, Cognito, DynamoDB
   - Lambda, API Gateway, S3, EC2
   - CloudWatch, IAM

## Quick Start (Mock Mode)

### 1. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd unreal-vr-multiplayer-system

# Install dependencies
npm install

# Install dependencies for all workspaces
npm run install:all
```

### 2. Start the Orchestrator

```bash
# Start orchestrator in mock mode
cd Orchestrator
npm run dev:mock

# Orchestrator will start on http://localhost:3000
```

### 3. Generate Your First Level

```bash
# In a new terminal, create a sample level
curl -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Create a VR arena with 2 combat zones and 1 safe zone. Players spawn in the safe zone and must capture objectives in combat zones for rewards.",
    "context": {
      "targetEnvironment": "dev"
    }
  }'

# This returns a planId - use it to execute the plan
curl -X POST http://localhost:3000/api/v1/plans/{planId}/execute \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### 4. Monitor Execution

```bash
# Check execution status
curl http://localhost:3000/api/v1/executions/{executionId}

# View generated artifacts in /Specs/examples/
ls -la Specs/examples/
```

## Local Development Setup

### Project Structure

```
unreal-vr-multiplayer-system/
├── Orchestrator/          # Local orchestration service
├── Agents/               # Specialized AI agents
├── MCP/                  # Model Context Protocol adapters
├── UnrealProject/        # UE5.3+ VR project
├── Infra/               # Terraform infrastructure
├── CI/                  # GitHub Actions workflows
├── Specs/               # Schemas and examples
└── tests/               # Test suites
```

### Environment Configuration

Create `.env` file in project root:

```bash
# Development environment settings
NODE_ENV=development
ORCHESTRATOR_PORT=3000
MOCK_MODE=true

# AWS settings (for staging/prod)
AWS_REGION=eu-west-1
AWS_PROFILE=default

# Cost monitoring
DEFAULT_BUDGET_LIMIT=1000
BUDGET_CURRENCY=GBP
COST_WARNING_THRESHOLD=0.8

# Agent configuration
AGENT_TIMEOUT=300000
MAX_RETRIES=3

# Unreal build settings
UNREAL_BUILD_MODE=mock  # Options: mock, cloud, local
EC2_INSTANCE_TYPE=g4dn.xlarge
BUILD_ARTIFACT_BUCKET=your-build-artifacts-bucket
```

### Running Individual Components

#### Orchestrator
```bash
cd Orchestrator
npm run dev        # Development mode
npm run dev:mock   # Mock mode (no external dependencies)
npm run test       # Run tests
npm run build      # Build for production
```

#### Agents
```bash
cd Agents
npm run dev        # Start all agents in development mode
npm run test       # Run agent tests
npm run test:properties  # Run property-based tests
```

#### MCP Adapters
```bash
cd MCP
npm run dev        # Start MCP adapters
npm run test:mock  # Test mock implementations
```

### Running Tests

#### Unit Tests
```bash
# Run all unit tests
npm run test:unit

# Run specific component tests
cd Orchestrator && npm test
cd Agents && npm test
cd MCP && npm test
```

#### Property-Based Tests
```bash
# Run all property tests (100 iterations each)
npm run test:properties

# Run specific property test
npm run test:properties -- --grep "Property 6: Reward Catalog Validation"
```

#### Integration Tests
```bash
# Run integration tests in mock mode
npm run test:integration

# Run vertical slice test
npm run test:vertical-slice
```

## Cloud Build Setup (Optional)

### AWS EC2 Build Configuration

If you want to use cloud builds instead of local Unreal Engine:

1. **Create Build AMI** (one-time setup):
```bash
cd Infra/modules/unreal-build
terraform init
terraform plan -var="create_ami=true"
terraform apply
```

2. **Configure Build Settings**:
```bash
# Update .env file
UNREAL_BUILD_MODE=cloud
EC2_INSTANCE_TYPE=g4dn.xlarge
BUILD_ARTIFACT_BUCKET=your-s3-bucket-name
```

3. **Test Cloud Build**:
```bash
# Trigger a test build
curl -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Build the current Unreal project for Quest 3",
    "context": {"targetEnvironment": "dev"}
  }'
```

### Local Unreal Engine Setup (Performance Optimization)

If you have Unreal Engine 5.3+ installed locally:

1. **Install UE5.3+** from Epic Games Launcher
2. **Configure Local Build**:
```bash
# Update .env file
UNREAL_BUILD_MODE=local
UNREAL_ENGINE_PATH=/path/to/UnrealEngine
```

3. **Verify Installation**:
```bash
# Test local build capability
cd UnrealProject
/path/to/UnrealEngine/Engine/Build/BatchFiles/RunUAT.bat BuildCookRun \
  -project=HyperMageVR.uproject \
  -platform=Android \
  -configuration=Development \
  -cook -build -stage -package
```

## Staging Environment Deployment

### 1. AWS Infrastructure Setup

```bash
cd Infra/environments/staging
terraform init
terraform plan
terraform apply
```

### 2. Configure Staging Environment

```bash
# Update .env for staging
NODE_ENV=staging
MOCK_MODE=false
AWS_REGION=eu-west-1
DEFAULT_BUDGET_LIMIT=100  # Lower limit for staging
```

### 3. Deploy and Test

```bash
# Start orchestrator in staging mode
npm run start:staging

# Test with real AWS services
curl -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Deploy a simple VR level to staging GameLift",
    "context": {"targetEnvironment": "staging"}
  }'
```

## Production Deployment

### 1. Production Infrastructure

```bash
cd Infra/environments/prod
terraform init
terraform plan  # Review changes carefully
# Manual approval required for production
terraform apply
```

### 2. Production Configuration

```bash
# Update .env for production
NODE_ENV=production
MOCK_MODE=false
DEFAULT_BUDGET_LIMIT=1000
APPROVAL_GATES_ENABLED=true
```

### 3. Production Deployment Process

```bash
# Production deployments require approval
npm run start:prod

# All operations will require manual approval
curl -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Deploy VR multiplayer level to production",
    "context": {"targetEnvironment": "prod"}
  }'

# System will pause for approval before executing
```

## Development Workflow

### 1. Create New Level

```bash
# Start with natural language specification
curl -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Create a medieval castle VR level with 4 towers, a central courtyard, and capture-the-flag objectives. Include voice chat for team coordination.",
    "context": {
      "targetEnvironment": "dev",
      "budgetPolicy": "./Specs/examples/BudgetPolicy.dev.json"
    }
  }'
```

### 2. Review Generated Plan

```bash
# Check the generated execution plan
curl http://localhost:3000/api/v1/plans/{planId}

# Review cost estimates and timeline
# Modify plan if needed before approval
```

### 3. Execute Plan

```bash
# Approve and execute the plan
curl -X POST http://localhost:3000/api/v1/plans/{planId}/execute \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### 4. Monitor Progress

```bash
# Watch execution progress
curl http://localhost:3000/api/v1/executions/{executionId}

# Check agent logs
tail -f Orchestrator/logs/orchestrator.log
tail -f Agents/logs/agents.log
```

### 5. Test Generated Level

```bash
# Run integration tests on generated level
npm run test:integration -- --level={levelId}

# Test VR comfort settings
npm run test:vr-comfort

# Test multiplayer functionality
npm run test:multiplayer
```

## Troubleshooting

### Common Issues

#### Orchestrator Won't Start
```bash
# Check Node.js version
node --version  # Should be 20+

# Check port availability
lsof -i :3000

# Check logs
tail -f Orchestrator/logs/orchestrator-error.log
```

#### Agent Timeouts
```bash
# Increase timeout in .env
AGENT_TIMEOUT=600000  # 10 minutes

# Check agent logs
tail -f Agents/logs/orchestrator.log
```

#### Cloud Build Failures
```bash
# Check EC2 instance logs
aws logs get-log-events \
  --log-group-name /aws/ec2/unreal-builds \
  --log-stream-name {instance-id}

# Verify S3 bucket permissions
aws s3 ls s3://your-build-artifacts-bucket
```

#### Cost Limit Exceeded
```bash
# Check current costs
curl http://localhost:3000/api/v1/costs/summary

# Adjust budget policy
vim Specs/examples/BudgetPolicy.dev.json

# Reset cost tracking (dev only)
curl -X DELETE http://localhost:3000/api/v1/costs/reset
```

### Debug Mode

Enable detailed logging:

```bash
# Set debug environment
DEBUG=orchestrator:*,agents:*,mcp:*
LOG_LEVEL=debug

# Start with verbose logging
npm run dev:debug
```

### Mock Mode Debugging

Test without external dependencies:

```bash
# Force mock mode for all adapters
MOCK_MODE=true
FORCE_MOCK=true

# Verify mock responses
curl http://localhost:3000/api/v1/mcp/test-all-mocks
```

## Next Steps

### Learn More
- Read [SPEC.md](./SPEC.md) for system architecture details
- Review [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md) for validation criteria
- Explore [Specs/examples/](./Specs/examples/) for sample configurations

### Extend the System
- Add new agents in `/Agents/` directory
- Create custom MCP adapters in `/MCP/adapters/`
- Define new schemas in `/Specs/schemas/`
- Add infrastructure modules in `/Infra/modules/`

### Contribute
- Run full test suite before submitting changes
- Follow property-based testing patterns
- Update documentation for new features
- Ensure cost tracking for new AWS operations

## Support

### Documentation
- System specification: [SPEC.md](./SPEC.md)
- API documentation: [Orchestrator/README.md](./Orchestrator/README.md)
- Agent documentation: [Agents/README.md](./Agents/README.md)

### Community
- GitHub Issues for bug reports
- GitHub Discussions for questions
- Contributing guidelines in [CONTRIBUTING.md](./CONTRIBUTING.md)

This getting started guide provides everything needed to begin developing with the Unreal VR Multiplayer System. The mock mode allows immediate experimentation without AWS costs, while the cloud build system ensures you can create production-ready VR experiences without local Unreal Engine installation.