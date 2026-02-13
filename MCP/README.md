# MCP - Model Context Protocol Adapters

## Overview

The MCP (Model Context Protocol) directory contains capability-based adapters that provide standardized interfaces to external systems. Each adapter implements both real and mock modes, enabling local development without external dependencies while maintaining production functionality.

## Architecture

### MCP Adapter Pattern

All MCP adapters follow a consistent pattern:

1. **Capability-Based Interface**: Agents request capabilities (e.g., "build_unreal_project") rather than direct API calls
2. **Mock Support**: Every adapter has a mock implementation for local development
3. **Provenance Tracking**: All operations are logged with timestamps and actor information
4. **Error Handling**: Consistent error reporting across all external systems
5. **Rate Limiting**: Prevents excessive API calls and cost overruns

### Base MCP Adapter

```typescript
export abstract class BaseMCPAdapter {
  protected mockMode: boolean;
  protected logger: Logger;
  protected costTracker: CostTracker;

  constructor(name: string, mockMode: boolean = false) {
    this.mockMode = mockMode;
    this.logger = createLogger(name);
    this.costTracker = new CostTracker();
  }

  abstract getCapabilities(): MCPCapability[];
  abstract executeCapability(capability: string, parameters: any): Promise<any>;
  
  protected async trackCost(operation: string, cost: number): Promise<void> {
    await this.costTracker.recordCost({
      service: this.constructor.name,
      operation,
      cost,
      timestamp: new Date().toISOString()
    });
  }
}
```

## MCP Adapters

### 1. UnrealMCP Adapter

**Purpose**: Unreal Engine operations (build, package, deploy)  
**File**: `adapters/UnrealMCPAdapter.ts`

**Capabilities**:

#### `build_project`
Compile Unreal Engine project for target platform.

**Parameters**:
```json
{
  "projectPath": "./UnrealProject/HyperMageVR.uproject",
  "platform": "Android",
  "configuration": "Development",
  "buildMode": "cloud"  // "cloud", "local", or "mock"
}
```

**Real Mode**: 
- Launches AWS EC2 g4dn.xlarge instance with UE5.3 AMI
- Clones project repository to instance
- Executes build commands
- Uploads artifacts to S3
- Terminates instance

**Mock Mode**:
- Simulates build process with realistic delays (2-5 minutes)
- Generates mock artifact metadata
- Returns mock S3 URLs

#### `package_server`
Package dedicated server build for GameLift deployment.

**Parameters**:
```json
{
  "buildPath": "./Builds/Server/",
  "gameMode": "HMVRGameMode",
  "maxPlayers": 15
}
```

#### `generate_level`
Generate Unreal map from LevelPlan specification.

**Parameters**:
```json
{
  "levelPlan": "./Specs/examples/castle-level.json",
  "outputPath": "./UnrealProject/Content/Maps/",
  "assetTier": 0  // 0=blockout, 1=placeholder, 2=final
}
```

#### `import_asset`
Import asset into Unreal project with provenance tracking.

**Parameters**:
```json
{
  "assetPath": "./assets/castle-wall.fbx",
  "targetPath": "/Game/Environment/Structures/",
  "provenance": {
    "origin": "generated",
    "license": "MIT",
    "createdBy": "TechArtVFXAudioAgent"
  }
}
```

### 2. AWSMCP Adapter

**Purpose**: AWS service operations (infrastructure, monitoring)  
**File**: `adapters/AWSMCPAdapter.ts`

**Capabilities**:

#### `deploy_gamelift`
Deploy GameLift fleet with server builds.

**Parameters**:
```json
{
  "fleetName": "vr-multiplayer-dev",
  "buildId": "build-12345",
  "instanceType": "c5.large",
  "maxInstances": 3,
  "region": "eu-west-1"
}
```

**Real Mode**: Uses AWS SDK to create GameLift resources
**Mock Mode**: Returns mock fleet ARN and status

#### `create_cognito_pool`
Set up Cognito User Pool for authentication.

**Parameters**:
```json
{
  "poolName": "vr-multiplayer-users",
  "jwtExpiration": 3600,
  "refreshExpiration": 604800,
  "mfaEnabled": false
}
```

#### `create_dynamodb_table`
Create DynamoDB table with TTL configuration.

**Parameters**:
```json
{
  "tableName": "PlayerSessions",
  "partitionKey": "playerId",
  "sortKey": "sessionId",
  "ttlAttribute": "ttl",
  "billingMode": "PAY_PER_REQUEST"
}
```

#### `monitor_costs`
Retrieve AWS cost and usage data.

**Parameters**:
```json
{
  "startDate": "2024-01-01",
  "endDate": "2024-01-31",
  "granularity": "DAILY",
  "groupBy": ["SERVICE"]
}
```

### 3. GitHubMCP Adapter

**Purpose**: Version control operations (commits, PRs, tags)  
**File**: `adapters/GitHubMCPAdapter.ts`

**Capabilities**:

#### `create_pr`
Create pull request with generated changes.

**Parameters**:
```json
{
  "title": "Add generated VR level: Castle Arena",
  "body": "Generated from specification: Medieval castle with 4 towers",
  "baseBranch": "main",
  "headBranch": "feature/castle-level",
  "files": [
    "./UnrealProject/Content/Maps/CastleArena.umap",
    "./Specs/examples/castle-level.json"
  ]
}
```

#### `commit_changes`
Commit specification updates and generated artifacts.

**Parameters**:
```json
{
  "message": "Update LevelPlan with new objectives",
  "files": [
    "./Specs/examples/updated-level.json"
  ],
  "author": {
    "name": "ConversationLevelDesignerAgent",
    "email": "agent@system.local"
  }
}
```

#### `create_tag`
Tag release with version information.

**Parameters**:
```json
{
  "tagName": "v1.2.0",
  "message": "Release: Castle Arena level with voice chat",
  "commitSha": "abc123def456"
}
```

### 4. LocalProcessMCP Adapter

**Purpose**: Local command execution (testing, validation)  
**File**: `adapters/LocalProcessMCPAdapter.ts`

**Capabilities**:

#### `execute_command`
Run local shell commands with timeout and logging.

**Parameters**:
```json
{
  "command": "npm test",
  "workingDirectory": "./Orchestrator",
  "timeout": 300000,
  "environment": {
    "NODE_ENV": "test"
  }
}
```

#### `validate_schemas`
Validate JSON files against schemas.

**Parameters**:
```json
{
  "schemaPath": "./Specs/schemas/LevelPlan.schema.json",
  "dataPath": "./Specs/examples/castle-level.json"
}
```

#### `run_tests`
Execute test suites with coverage reporting.

**Parameters**:
```json
{
  "testType": "unit",  // "unit", "integration", "properties"
  "testPath": "./tests/",
  "coverage": true,
  "parallel": false
}
```

## Configuration

### Environment Variables

```bash
# MCP Configuration
MCP_BASE_PORT=4000
MCP_TIMEOUT=300000
MCP_MAX_RETRIES=3

# Mock Mode
MOCK_MODE=false
MOCK_DELAY_MIN=1000
MOCK_DELAY_MAX=5000

# AWS Configuration (for AWSMCP)
AWS_REGION=eu-west-1
AWS_PROFILE=default

# GitHub Configuration (for GitHubMCP)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_OWNER=your-username
GITHUB_REPO=unreal-vr-multiplayer-system

# Unreal Configuration (for UnrealMCP)
UNREAL_BUILD_MODE=cloud  # "cloud", "local", "mock"
EC2_INSTANCE_TYPE=g4dn.xlarge
BUILD_ARTIFACT_BUCKET=your-build-bucket
UNREAL_ENGINE_PATH=/opt/UnrealEngine  # For local builds
```

### Adapter Configuration Files

Each adapter can have a configuration file in `./config/`:

```json
{
  "name": "UnrealMCPAdapter",
  "port": 4001,
  "mockMode": false,
  "capabilities": {
    "build_project": {
      "timeout": 600000,
      "costPerBuild": 2.50,
      "ec2InstanceType": "g4dn.xlarge"
    },
    "package_server": {
      "timeout": 300000,
      "costPerPackage": 1.00
    }
  },
  "aws": {
    "region": "eu-west-1",
    "s3Bucket": "vr-build-artifacts"
  }
}
```

## Development

### Setup

```bash
cd MCP
npm install
npm run build
```

### Running MCP Adapters

```bash
# Start all adapters
npm run dev

# Start specific adapter
npm run dev:adapter -- --name=UnrealMCPAdapter

# Start in mock mode
npm run dev:mock

# Production mode
npm run start
```

### Testing MCP Adapters

```bash
# Unit tests
npm test

# Mock mode tests
npm run test:mock

# Integration tests (requires real services)
npm run test:integration

# Test specific adapter
npm test -- --grep "UnrealMCPAdapter"
```

### Creating New MCP Adapters

1. **Create Adapter Class**:
```typescript
import { BaseMCPAdapter } from '../BaseMCPAdapter';

export class MyCustomMCPAdapter extends BaseMCPAdapter {
  constructor(mockMode: boolean = false) {
    super('MyCustomMCPAdapter', mockMode);
  }

  getCapabilities(): MCPCapability[] {
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
        estimatedCost: 1.00,
        estimatedDuration: 5000
      }
    ];
  }

  async executeCapability(capability: string, parameters: any): Promise<any> {
    if (this.mockMode) {
      return this.executeMockCapability(capability, parameters);
    }

    switch (capability) {
      case 'my_capability':
        return this.handleMyCapability(parameters);
      default:
        throw new Error(`Unknown capability: ${capability}`);
    }
  }

  private async handleMyCapability(params: any): Promise<any> {
    // Real implementation
    await this.trackCost('my_capability', 1.00);
    return { success: true, result: 'done' };
  }

  private async executeMockCapability(capability: string, params: any): Promise<any> {
    // Mock implementation
    await this.simulateDelay(2000);
    return { success: true, result: 'mock_result' };
  }
}
```

2. **Register Adapter**:
```typescript
// In index.ts
import { MyCustomMCPAdapter } from './adapters/MyCustomMCPAdapter';

const adapters = [
  // ... existing adapters
  new MyCustomMCPAdapter(process.env.MOCK_MODE === 'true')
];
```

## Mock Mode Implementation

### Mock Response Generation

Mock adapters generate realistic responses with appropriate delays:

```typescript
class MockResponseGenerator {
  static generateBuildArtifact(): BuildArtifact {
    return {
      buildId: `build-${Date.now()}`,
      platform: 'Android',
      configuration: 'Development',
      artifactUrl: `s3://mock-bucket/builds/build-${Date.now()}.zip`,
      size: Math.floor(Math.random() * 1000000000), // Random size
      checksum: this.generateMockChecksum(),
      buildTime: Math.floor(Math.random() * 300) + 60 // 1-6 minutes
    };
  }

  static generateGameLiftFleet(): GameLiftFleet {
    return {
      fleetId: `fleet-${this.generateId()}`,
      fleetArn: `arn:aws:gamelift:eu-west-1:123456789012:fleet/fleet-${this.generateId()}`,
      status: 'ACTIVE',
      instanceType: 'c5.large',
      currentInstances: Math.floor(Math.random() * 3) + 1
    };
  }
}
```

### Mock Delay Simulation

```typescript
protected async simulateDelay(baseDelay: number = 2000): Promise<void> {
  const minDelay = parseInt(process.env.MOCK_DELAY_MIN || '1000');
  const maxDelay = parseInt(process.env.MOCK_DELAY_MAX || '5000');
  const delay = Math.floor(Math.random() * (maxDelay - minDelay)) + minDelay;
  
  await new Promise(resolve => setTimeout(resolve, delay));
}
```

## Monitoring and Observability

### Health Checks

Each adapter exposes health endpoints:

```bash
# Individual adapter health
curl http://localhost:4001/health

# All adapters health
curl http://localhost:4000/health/all
```

### Metrics

Key metrics tracked per adapter:

- Capability execution count and success rate
- Average response time per capability
- Cost per operation
- Error rate by capability type
- External API rate limiting status

### Logging

Structured logging with operation tracking:

```typescript
this.logger.info('Capability executed', {
  adapter: 'UnrealMCPAdapter',
  capability: 'build_project',
  parameters: { platform: 'Android' },
  duration: 125000,
  cost: 2.50,
  success: true,
  mockMode: this.mockMode
});
```

## Cost Tracking Integration

### Cost Recording

All adapters integrate with the CostMonitorFinOpsAgent:

```typescript
protected async trackCost(operation: string, cost: number, resourceId?: string): Promise<void> {
  const costRecord = {
    service: this.constructor.name,
    operation,
    cost,
    currency: 'GBP',
    timestamp: new Date().toISOString(),
    resourceId,
    mockMode: this.mockMode
  };

  await this.costTracker.recordCost(costRecord);
}
```

### Cost Estimation

Capabilities provide cost estimates:

```typescript
getCapabilities(): MCPCapability[] {
  return [
    {
      name: 'build_project',
      estimatedCost: 2.50, // EC2 instance cost
      costFactors: {
        'g4dn.xlarge': 0.526, // per hour
        's3_storage': 0.023,  // per GB
        'data_transfer': 0.09 // per GB
      }
    }
  ];
}
```

## Deployment

### Local Development

```bash
# Start all adapters with hot reload
npm run dev

# Start with specific configuration
NODE_ENV=development MOCK_MODE=true npm run dev
```

### Production Deployment

```bash
# Build all adapters
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
EXPOSE 4000-4010
CMD ["npm", "start"]
```

## Troubleshooting

### Common Issues

#### Adapter Not Responding
```bash
# Check adapter health
curl http://localhost:4001/health

# Check logs
tail -f logs/mcp.log

# Restart specific adapter
pm2 restart UnrealMCPAdapter
```

#### AWS Credentials Issues
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check IAM permissions
aws iam get-user

# Test specific service access
aws gamelift describe-fleets
```

#### Mock Mode Not Working
```bash
# Verify mock mode environment
echo $MOCK_MODE

# Force mock mode
MOCK_MODE=true npm run dev

# Check mock response generation
curl -X POST http://localhost:4001/capabilities/build_project \
  -H "Content-Type: application/json" \
  -d '{"platform": "Android"}'
```

This MCP adapter framework provides a robust, testable interface to external systems while maintaining cost control and comprehensive monitoring capabilities.