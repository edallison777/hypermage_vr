# Orchestrator - Local-First Orchestration Service

## Overview

The Orchestrator is the central coordination service for the Unreal VR Multiplayer System. It implements a local-first architecture that runs on developer machines, managing the plan→execute workflow and coordinating multiple specialized agents to transform natural language specifications into deployed VR experiences.

## Architecture

### Core Components

- **Plan Generator**: Analyzes natural language specifications and creates structured execution plans
- **Plan Executor**: Coordinates agent execution according to dependency order
- **Agent Communication**: HTTP/JSON message routing with correlation IDs and timeout handling
- **State Persistence**: SQLite database for execution history and state management
- **Cost Integration**: Real-time cost tracking and budget enforcement via CostMonitorFinOpsAgent

### API Endpoints

#### POST /api/v1/plans
Create execution plan from natural language specification.

**Request:**
```json
{
  "specification": "Create a VR arena with 3 combat zones and 2 safe zones...",
  "context": {
    "existingLevels": ["level1", "level2"],
    "budgetPolicy": "./policies/dev-budget.json",
    "targetEnvironment": "dev"
  }
}
```

**Response:**
```json
{
  "planId": "uuid",
  "steps": [
    {
      "id": "step1",
      "agent": "ConversationLevelDesignerAgent",
      "capability": "generate_level_plan",
      "parameters": {...},
      "dependencies": [],
      "estimatedCost": 5.50,
      "estimatedDuration": "2m"
    }
  ],
  "estimatedCost": 45.75,
  "estimatedDuration": "15m"
}
```

#### POST /api/v1/plans/:planId/execute
Execute approved plan with optional modifications.

**Request:**
```json
{
  "approved": true,
  "modifications": [
    {
      "stepId": "step3",
      "parameters": {"buildMode": "cloud"}
    }
  ]
}
```

**Response:**
```json
{
  "executionId": "uuid",
  "status": "running",
  "progress": {
    "completed": 2,
    "total": 8,
    "currentStep": "Building Unreal project"
  }
}
```

#### GET /api/v1/executions/:executionId
Get execution status and progress.

**Response:**
```json
{
  "executionId": "uuid",
  "planId": "uuid",
  "status": "completed",
  "steps": [
    {
      "id": "step1",
      "status": "completed",
      "startTime": "2024-01-15T10:30:00Z",
      "endTime": "2024-01-15T10:32:15Z",
      "result": {...},
      "cost": 5.50
    }
  ],
  "artifacts": [
    {
      "type": "LevelPlan",
      "path": "./Specs/examples/generated-level.json",
      "url": "s3://bucket/artifacts/level-plan.json"
    }
  ],
  "costs": {
    "total": 42.30,
    "byService": {
      "gamelift": 25.00,
      "ec2": 15.50,
      "s3": 1.80
    }
  }
}
```

## Configuration

### Environment Variables

```bash
# Server configuration
NODE_ENV=development
ORCHESTRATOR_PORT=3000
LOG_LEVEL=info

# Database
DATABASE_PATH=./data/orchestrator.db
DATABASE_BACKUP_INTERVAL=3600000  # 1 hour

# Agent communication
AGENT_TIMEOUT=300000  # 5 minutes
MAX_RETRIES=3
RETRY_DELAY=5000

# Cost monitoring
COST_TRACKING_ENABLED=true
BUDGET_CHECK_INTERVAL=60000  # 1 minute

# Mock mode
MOCK_MODE=false
MOCK_DELAY_MIN=1000
MOCK_DELAY_MAX=5000
```

### Budget Policy Configuration

```json
{
  "id": "dev-policy",
  "environment": "dev",
  "limits": {
    "total": 100,
    "currency": "GBP",
    "duration": "24h",
    "perService": {
      "gamelift": 40,
      "ec2": 30,
      "dynamodb": 20,
      "other": 10
    }
  },
  "enforcement": {
    "mode": "warn",
    "warningThreshold": 0.8,
    "approvalRequired": false
  }
}
```

## Development

### Setup

```bash
cd Orchestrator
npm install
npm run build
```

### Running

```bash
# Development mode with hot reload
npm run dev

# Mock mode (no external dependencies)
npm run dev:mock

# Production mode
npm run start

# Debug mode with verbose logging
DEBUG=orchestrator:* npm run dev
```

### Testing

```bash
# Unit tests
npm test

# Integration tests
npm run test:integration

# Property-based tests
npm run test:properties

# Test coverage
npm run test:coverage
```

## Agent Integration

### Agent Communication Protocol

The Orchestrator communicates with agents via HTTP/JSON:

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

### Agent Registration

Agents register their capabilities with the Orchestrator:

```typescript
interface AgentCapability {
  name: string;
  description: string;
  parameters: JSONSchema;
  estimatedCost: number;
  estimatedDuration: number;
  dependencies: string[];
}
```

### Error Handling

The Orchestrator implements comprehensive error handling:

- **Agent Timeout**: Retry up to 3 times with exponential backoff
- **Agent Error**: Mark step as failed, pause execution for user intervention
- **Dependency Failure**: Skip dependent steps, continue with independent steps
- **Cost Limit Exceeded**: Block execution, notify user, require budget approval

## State Management

### SQLite Schema

```sql
-- Execution plans
CREATE TABLE plans (
  id TEXT PRIMARY KEY,
  specification TEXT NOT NULL,
  context JSON,
  steps JSON NOT NULL,
  estimated_cost REAL,
  estimated_duration INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Plan executions
CREATE TABLE executions (
  id TEXT PRIMARY KEY,
  plan_id TEXT REFERENCES plans(id),
  status TEXT NOT NULL,
  started_at DATETIME,
  completed_at DATETIME,
  error_message TEXT
);

-- Step executions
CREATE TABLE step_executions (
  id TEXT PRIMARY KEY,
  execution_id TEXT REFERENCES executions(id),
  step_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at DATETIME,
  completed_at DATETIME,
  result JSON,
  error_message TEXT,
  cost REAL
);

-- Agent messages
CREATE TABLE agent_messages (
  id TEXT PRIMARY KEY,
  execution_id TEXT REFERENCES executions(id),
  step_id TEXT,
  direction TEXT NOT NULL, -- 'request' or 'response'
  agent TEXT NOT NULL,
  message JSON NOT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### State Persistence

- **Plans**: Stored indefinitely for audit trail
- **Executions**: Stored for 30 days (configurable)
- **Agent Messages**: Stored for 7 days (configurable)
- **Artifacts**: Referenced by path/URL, not stored in database

## Monitoring and Observability

### Logging

Structured JSON logging with Winston:

```typescript
logger.info('Plan execution started', {
  executionId: 'uuid',
  planId: 'uuid',
  agentCount: 5,
  estimatedCost: 45.75,
  correlationId: 'uuid'
});
```

### Metrics

Key metrics tracked:

- Plan generation time
- Execution success rate
- Agent response time
- Cost accuracy (estimated vs actual)
- Error rate by agent

### Health Checks

```bash
# Health endpoint
curl http://localhost:3000/health

# Detailed status
curl http://localhost:3000/api/v1/status
```

## Deployment

### Local Development

```bash
# Start with mock agents
npm run dev:mock

# Start with real agents (requires agent services running)
npm run dev
```

### Production Deployment

```bash
# Build production bundle
npm run build

# Start production server
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
EXPOSE 3000
CMD ["npm", "start"]
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process using port 3000
lsof -i :3000
kill -9 <PID>
```

#### Database Locked
```bash
# Check for zombie connections
sqlite3 data/orchestrator.db ".timeout 1000"
```

#### Agent Timeouts
```bash
# Increase timeout in environment
AGENT_TIMEOUT=600000  # 10 minutes

# Check agent logs
curl http://localhost:3001/health  # Agent health check
```

#### Memory Issues
```bash
# Monitor memory usage
node --max-old-space-size=4096 dist/server.js

# Enable garbage collection logging
node --trace-gc dist/server.js
```

### Debug Mode

```bash
# Enable debug logging
DEBUG=orchestrator:* npm run dev

# Specific debug categories
DEBUG=orchestrator:plan,orchestrator:execute npm run dev

# Log all HTTP requests
DEBUG=orchestrator:*,express:* npm run dev
```

## API Examples

### Complete Workflow Example

```bash
# 1. Create plan
PLAN_ID=$(curl -s -X POST http://localhost:3000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Create a medieval VR castle with 4 towers and courtyard",
    "context": {"targetEnvironment": "dev"}
  }' | jq -r '.planId')

# 2. Review plan
curl http://localhost:3000/api/v1/plans/$PLAN_ID | jq

# 3. Execute plan
EXECUTION_ID=$(curl -s -X POST http://localhost:3000/api/v1/plans/$PLAN_ID/execute \
  -H "Content-Type: application/json" \
  -d '{"approved": true}' | jq -r '.executionId')

# 4. Monitor progress
watch "curl -s http://localhost:3000/api/v1/executions/$EXECUTION_ID | jq '.progress'"
```

This Orchestrator provides the foundation for coordinating complex multi-agent workflows while maintaining local-first operation and comprehensive state management.