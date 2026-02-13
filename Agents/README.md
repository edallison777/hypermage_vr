# Agents - Specialized AI Components

## Overview

The Agents directory contains 10 specialized AI agents that handle different aspects of VR multiplayer level creation and deployment. Each agent is responsible for a specific domain and communicates with the Orchestrator through a standardized HTTP/JSON protocol.

## Agent Architecture

### Base Agent Framework

All agents inherit from `BaseAgent` which provides:

- **HTTP Server**: Express.js server for receiving orchestrator requests
- **Capability Registration**: Automatic capability discovery and registration
- **Error Handling**: Standardized error responses and logging
- **Timeout Management**: Request timeout handling and graceful shutdown
- **Cost Tracking**: Integration with CostMonitorFinOpsAgent for operation costs

### Agent Communication Protocol

```typescript
interface AgentRequest {
  id: string;
  timestamp: string;
  capability: string;
  parameters: Record<string, any>;
  timeout?: number;
  correlationId: string;
}

interface AgentResponse {
  id: string;
  timestamp: string;
  success: boolean;
  result?: any;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  cost?: number;
  correlationId: string;
}
```

## Agent Specifications

### 1. ProducerOrchestratorAgent
**Port**: 3001  
**Responsibilities**: Task decomposition, milestone gating, reward catalog enforcement

**Capabilities**:
- `decompose_specification`: Break down natural language into structured tasks
- `validate_milestones`: Ensure completion criteria are met before proceeding
- `enforce_reward_catalog`: Validate reward IDs against catalog

**Example Request**:
```json
{
  "capability": "decompose_specification",
  "parameters": {
    "specification": "Create a VR arena with combat zones",
    "context": {"targetEnvironment": "dev"}
  }
}
```

### 2. ConversationLevelDesignerAgent
**Port**: 3002  
**Responsibilities**: Natural language to LevelPlan conversion, zone layout generation

**Capabilities**:
- `generate_level_plan`: Convert natural language to structured LevelPlan.json
- `optimize_layout`: Improve zone placement for VR comfort
- `validate_spawns`: Ensure spawn points are accessible and balanced

**Example Request**:
```json
{
  "capability": "generate_level_plan",
  "parameters": {
    "description": "Medieval castle with 4 towers and central courtyard",
    "playerCount": 15,
    "objectives": ["capture_flag", "defend_base"]
  }
}
```

### 3. UnrealLevelBuilderAgent
**Port**: 3003  
**Responsibilities**: LevelPlan to Unreal map conversion, blockout geometry generation

**Capabilities**:
- `build_level_geometry`: Generate Unreal map from LevelPlan
- `place_spawns`: Position player spawn points
- `setup_objectives`: Create objective triggers and logic

**Example Request**:
```json
{
  "capability": "build_level_geometry",
  "parameters": {
    "levelPlan": "./Specs/examples/castle-level.json",
    "outputPath": "./UnrealProject/Content/Maps/",
    "buildMode": "blockout"
  }
}
```

### 4. GameplaySystemsAgent
**Port**: 3004  
**Responsibilities**: VR interaction systems, objective implementation, server-side reward emission

**Capabilities**:
- `implement_vr_interactions`: Create VR-specific interaction systems
- `setup_objectives`: Implement objective capture logic
- `configure_rewards`: Set up server-side reward granting

**Example Request**:
```json
{
  "capability": "implement_vr_interactions",
  "parameters": {
    "interactionTypes": ["grab", "teleport", "point"],
    "comfortSettings": {
      "snapTurn": true,
      "vignette": true,
      "teleportFallback": true
    }
  }
}
```

### 5. MultiplayerNetcodeAgent
**Port**: 3005  
**Responsibilities**: Server-authoritative networking, replication strategy, bandwidth management

**Capabilities**:
- `setup_replication`: Configure server-client replication
- `implement_authority`: Ensure server authority for gameplay
- `optimize_bandwidth`: Manage network traffic for VR performance

**Example Request**:
```json
{
  "capability": "setup_replication",
  "parameters": {
    "maxPlayers": 15,
    "tickRate": 60,
    "compressionLevel": "medium"
  }
}
```

### 6. VoiceCommsAgent
**Port**: 3006  
**Responsibilities**: Party voice integration, audio routing, mute/block controls

**Capabilities**:
- `setup_voice_chat`: Configure Unreal Voice Chat Interface
- `implement_party_voice`: Set up party-wide voice communication
- `add_voice_controls`: Implement mute/block functionality

**Example Request**:
```json
{
  "capability": "setup_voice_chat",
  "parameters": {
    "provider": "mock",
    "partySize": 15,
    "spatialAudio": false
  }
}
```

### 7. TechArtVFXAudioAgent
**Port**: 3007  
**Responsibilities**: Tier 1 asset generation, Quest 3 optimization, spatial audio configuration

**Capabilities**:
- `generate_tier1_assets`: Create placeholder assets from concept art
- `optimize_for_quest3`: Optimize materials and LODs for Quest 3
- `setup_spatial_audio`: Configure 3D audio for VR

**Example Request**:
```json
{
  "capability": "generate_tier1_assets",
  "parameters": {
    "conceptArt": "./assets/concept/castle-tower.jpg",
    "assetType": "mesh",
    "targetTier": 1
  }
}
```

### 8. AssetPipelineAgent
**Port**: 3008  
**Responsibilities**: Asset import validation, provenance tracking, licensed asset recommendations

**Capabilities**:
- `validate_asset_import`: Check asset format and metadata
- `track_provenance`: Create and maintain provenance records
- `recommend_licensed_assets`: Suggest marketplace assets without purchasing

**Example Request**:
```json
{
  "capability": "validate_asset_import",
  "parameters": {
    "assetPath": "./assets/imported/castle-wall.fbx",
    "requireProvenance": true,
    "licenseCheck": true
  }
}
```

### 9. QAAgent
**Port**: 3009  
**Responsibilities**: Test generation, multiplayer validation, VR comfort verification

**Capabilities**:
- `generate_unit_tests`: Create unit tests for gameplay systems
- `validate_vr_comfort`: Test VR comfort settings and accessibility
- `run_multiplayer_tests`: Execute multiplayer integration tests

**Example Request**:
```json
{
  "capability": "validate_vr_comfort",
  "parameters": {
    "testScenarios": ["rapid_movement", "rotation", "teleport"],
    "comfortSettings": {
      "vignette": true,
      "snapTurn": true
    }
  }
}
```

### 10. DevOpsAWSAgent
**Port**: 3010  
**Responsibilities**: Terraform orchestration, CI/CD management, observability setup

**Capabilities**:
- `deploy_infrastructure`: Execute Terraform plans for AWS resources
- `setup_cicd`: Configure GitHub Actions workflows
- `configure_monitoring`: Set up CloudWatch and alerting

**Example Request**:
```json
{
  "capability": "deploy_infrastructure",
  "parameters": {
    "environment": "dev",
    "terraformPlan": "./Infra/environments/dev/",
    "autoApprove": false
  }
}
```

### 11. CostMonitorFinOpsAgent (Mandatory)
**Port**: 3011  
**Responsibilities**: Real-time cost tracking, budget enforcement, cost reporting

**Capabilities**:
- `track_operation_cost`: Record costs for AWS operations
- `check_budget_limits`: Validate operations against budget policy
- `generate_cost_report`: Create detailed cost breakdowns

**Example Request**:
```json
{
  "capability": "check_budget_limits",
  "parameters": {
    "operation": "deploy_gamelift_fleet",
    "estimatedCost": 25.50,
    "budgetPolicy": "./policies/dev-budget.json"
  }
}
```

## Development

### Setup

```bash
cd Agents
npm install
npm run build
```

### Running Agents

```bash
# Start all agents in development mode
npm run dev

# Start specific agent
npm run dev:agent -- --name=ConversationLevelDesignerAgent

# Start agents in mock mode
npm run dev:mock

# Production mode
npm run start
```

### Creating New Agents

1. **Create Agent Class**:
```typescript
import { BaseAgent } from './BaseAgent';

export class MyCustomAgent extends BaseAgent {
  constructor() {
    super('MyCustomAgent', 3012);
  }

  async executeCapability(capability: string, parameters: any): Promise<any> {
    switch (capability) {
      case 'my_capability':
        return this.handleMyCapability(parameters);
      default:
        throw new Error(`Unknown capability: ${capability}`);
    }
  }

  private async handleMyCapability(params: any): Promise<any> {
    // Implementation here
    return { success: true, result: 'done' };
  }
}
```

2. **Register Capabilities**:
```typescript
getCapabilities(): AgentCapability[] {
  return [
    {
      name: 'my_capability',
      description: 'Does something useful',
      parameters: {
        type: 'object',
        properties: {
          input: { type: 'string' }
        },
        required: ['input']
      },
      estimatedCost: 1.50,
      estimatedDuration: 30000
    }
  ];
}
```

3. **Add to Agent Registry**:
```typescript
// In index.ts
import { MyCustomAgent } from './MyCustomAgent';

const agents = [
  // ... existing agents
  new MyCustomAgent()
];
```

### Testing

```bash
# Unit tests for all agents
npm test

# Property-based tests
npm run test:properties

# Integration tests
npm run test:integration

# Test specific agent
npm test -- --grep "ConversationLevelDesignerAgent"
```

### Agent Testing Framework

```typescript
import { AgentTestHarness } from './test/AgentTestHarness';

describe('ConversationLevelDesignerAgent', () => {
  let harness: AgentTestHarness;

  beforeEach(() => {
    harness = new AgentTestHarness('ConversationLevelDesignerAgent');
  });

  it('should generate valid LevelPlan', async () => {
    const result = await harness.executeCapability('generate_level_plan', {
      description: 'Simple arena',
      playerCount: 10
    });

    expect(result.success).toBe(true);
    expect(result.result).toHaveProperty('zones');
    expect(result.result).toHaveProperty('playerSpawns');
  });
});
```

## Configuration

### Environment Variables

```bash
# Agent configuration
AGENT_BASE_PORT=3001
AGENT_TIMEOUT=300000
MAX_CONCURRENT_REQUESTS=10

# Logging
LOG_LEVEL=info
LOG_FORMAT=json

# Cost tracking
COST_TRACKING_ENABLED=true
COST_MONITOR_AGENT_URL=http://localhost:3011

# Mock mode
MOCK_MODE=false
MOCK_RESPONSE_DELAY=2000
```

### Agent Configuration Files

Each agent can have a configuration file in `./config/`:

```json
{
  "name": "ConversationLevelDesignerAgent",
  "port": 3002,
  "capabilities": {
    "generate_level_plan": {
      "timeout": 120000,
      "maxRetries": 3,
      "costPerRequest": 2.50
    }
  },
  "dependencies": {
    "imageGeneration": "http://localhost:3020",
    "assetValidation": "http://localhost:3008"
  }
}
```

## Monitoring and Observability

### Health Checks

Each agent exposes health endpoints:

```bash
# Individual agent health
curl http://localhost:3002/health

# All agents health
curl http://localhost:3001/health/all
```

### Metrics

Key metrics tracked per agent:

- Request count and success rate
- Average response time
- Error rate by capability
- Cost per operation
- Resource utilization

### Logging

Structured logging with correlation IDs:

```typescript
this.logger.info('Capability executed', {
  agent: 'ConversationLevelDesignerAgent',
  capability: 'generate_level_plan',
  correlationId: 'uuid',
  duration: 2500,
  cost: 2.50,
  success: true
});
```

## Deployment

### Local Development

```bash
# Start all agents with hot reload
npm run dev

# Start with specific configuration
NODE_ENV=development npm run dev
```

### Production Deployment

```bash
# Build all agents
npm run build

# Start production servers
npm run start

# With PM2 process manager
pm2 start ecosystem.config.js
```

### Docker Deployment

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY dist/ ./dist/
EXPOSE 3001-3011
CMD ["npm", "start"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vr-agents
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vr-agents
  template:
    metadata:
      labels:
        app: vr-agents
    spec:
      containers:
      - name: agents
        image: vr-agents:latest
        ports:
        - containerPort: 3001
        - containerPort: 3002
        # ... other ports
        env:
        - name: NODE_ENV
          value: "production"
```

## Troubleshooting

### Common Issues

#### Agent Not Responding
```bash
# Check agent health
curl http://localhost:3002/health

# Check logs
tail -f logs/agents.log

# Restart specific agent
pm2 restart ConversationLevelDesignerAgent
```

#### High Memory Usage
```bash
# Monitor memory per agent
ps aux | grep node

# Enable garbage collection logging
node --trace-gc dist/ConversationLevelDesignerAgent.js
```

#### Capability Timeouts
```bash
# Increase timeout in agent config
{
  "capabilities": {
    "generate_level_plan": {
      "timeout": 300000  // 5 minutes
    }
  }
}
```

This agent framework provides a scalable, maintainable architecture for specialized AI components with comprehensive monitoring, testing, and deployment capabilities.