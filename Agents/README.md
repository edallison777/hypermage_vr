# Agents

This directory contains specialized AI agents built with [Strands Agent SDK](https://strandsagents.com) for the Unreal VR Multiplayer System.

## Overview

All agents are built using the Strands Agent SDK and deployed to AWS Bedrock AgentCore Runtime. Each agent is responsible for a specific domain and communicates through structured JSON messages coordinated by the Orchestrator.

## Architecture

### Base Agent

The `BaseAgent` class provides common functionality for all specialized agents:

- **Strands SDK Integration**: Uses Strands Agent SDK with Amazon Bedrock models
- **MCP Adapter Communication**: Interfaces with external systems through MCP adapters
- **Cost Tracking**: Records costs for all operations
- **Error Handling**: Consistent error handling and retry logic
- **Provenance Logging**: Tracks all operations for audit trail

### Specialized Agents

Each specialized agent extends `BaseAgent` and implements domain-specific capabilities:

1. **ProducerOrchestratorAgent** - Task decomposition and milestone gating
2. **ConversationLevelDesignerAgent** - Natural language to LevelPlan conversion
3. **UnrealLevelBuilderAgent** - LevelPlan to Unreal map conversion
4. **GameplaySystemsAgent** - VR interaction and objective implementation
5. **MultiplayerNetcodeAgent** - Replication and networking
6. **VoiceCommsAgent** - Party voice integration
7. **TechArtVFXAudioAgent** - Asset generation and optimization
8. **AssetPipelineAgent** - Asset import and provenance tracking
9. **QAAgent** - Test generation and validation
10. **DevOpsAWSAgent** - Infrastructure deployment
11. **CostMonitorFinOpsAgent** - Cost monitoring and budget enforcement

## Usage

### Creating a New Agent

```typescript
import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';

export class MyAgent extends BaseAgent {
    constructor(mcpAdapters = []) {
        const config: AgentConfig = {
            name: 'my-agent',
            description: 'Description of what this agent does',
            capabilities: [
                {
                    name: 'my_capability',
                    description: 'What this capability does',
                    parameters: {
                        // JSON Schema for parameters
                    },
                    mcpAdapters: ['UnrealMCP', 'AWSMCP'],
                },
            ],
        };
        super(config, mcpAdapters);
    }

    protected getSystemPrompt(): string {
        return `You are MyAgent, responsible for...`;
    }
}
```

### Invoking an Agent

```typescript
import { MyAgent } from './MyAgent.js';

const agent = new MyAgent(mcpAdapters);

const context: AgentContext = {
    executionId: 'exec-123',
    planId: 'plan-456',
    stepId: 'step-789',
    environment: 'dev',
};

const result = await agent.invoke('Create a new level', context);

if (result.success) {
    console.log('Result:', result.result);
    console.log('Costs:', result.costs);
} else {
    console.error('Error:', result.error);
}
```

### Using MCP Adapters

```typescript
protected async myMethod(context: AgentContext): Promise<void> {
    // Call Unreal MCP adapter
    const response = await this.callMCP(
        'UnrealMCP',
        'generate_level',
        {
            levelPlanPath: '/path/to/level-plan.json',
        },
        context
    );

    if (response.success) {
        console.log('Level generated:', response.result);
    }
}
```

## Development

### Setup

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Watch mode for development
npm run dev
```

### Testing

```bash
# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

## Deployment to AWS Bedrock AgentCore

Each agent can be deployed to AWS Bedrock AgentCore Runtime for production use. See the [Strands deployment guide](https://strandsagents.com/latest/documentation/docs/user-guide/deploy/deploy_to_bedrock_agentcore/typescript/) for details.

### Prerequisites

- AWS account with Bedrock access
- IAM role with appropriate permissions
- ECR repository for Docker images
- Docker installed locally

### Deployment Steps

1. Build the agent Docker image
2. Push to ECR
3. Create AgentCore runtime
4. Test the deployment

See individual agent directories for specific deployment instructions.

## Configuration

### Model Configuration

Agents use Amazon Bedrock by default with Claude 4 Sonnet:

```typescript
const config: AgentConfig = {
    model: {
        provider: 'bedrock',
        modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
        region: 'eu-west-1',
        temperature: 0.7,
        maxTokens: 4096,
    },
    // ...
};
```

### MCP Adapters

Agents communicate with external systems through MCP adapters:

- **UnrealMCP**: Unreal Engine operations
- **AWSMCP**: AWS service operations
- **GitHubMCP**: Version control operations
- **LocalProcessMCP**: Local command execution
- **ImageGenMCP**: Image generation
- **AudioGenMCP**: Audio generation

## Cost Tracking

All agents track costs for operations:

```typescript
// Costs are automatically tracked for MCP calls
const result = await agent.invoke(prompt, context);
console.log('Total cost:', result.costs?.reduce((sum, c) => sum + c.cost, 0));
```

## Error Handling

Agents provide consistent error handling:

```typescript
const result = await agent.invoke(prompt, context);

if (!result.success) {
    console.error('Error code:', result.error?.code);
    console.error('Error message:', result.error?.message);
    console.error('Retryable:', result.error?.retryable);
}
```

## Provenance

All agent operations are logged for audit trail:

```typescript
const result = await agent.invoke(prompt, context);

// MCP calls are recorded
for (const call of result.mcpCalls || []) {
    console.log('MCP call:', call.adapter, call.capability);
    console.log('Duration:', call.duration, 'ms');
}
```

## License

UNLICENSED - Private project
