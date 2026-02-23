# Agent Examples - Strands SDK Integration

This directory contains example agents that demonstrate proper Strands SDK integration patterns.

## Simple Calculator Agent

The `SimpleCalculatorAgent` is a minimal reference implementation that shows how to:

1. **Initialize a Strands Agent** with Amazon Bedrock
2. **Define and register tools** that the agent can use
3. **Handle agent invocations** with proper error handling
4. **Maintain conversation context** across multiple interactions
5. **Track costs and performance** for operations
6. **Implement capabilities** with structured parameters

### Key Features

- **Minimal Complexity**: Focuses on core Strands SDK patterns without production complexity
- **Well-Documented**: Extensive comments explaining each pattern
- **Runnable Example**: Includes a complete example script
- **Production Patterns**: Uses the same BaseAgent class as production agents

### File Structure

```
Agents/
├── SimpleCalculatorAgent.ts          # The agent implementation
├── examples/
│   ├── README.md                     # This file
│   └── simple-calculator-example.ts  # Usage examples
└── BaseAgent.ts                      # Base class with Strands integration
```

## Quick Start

### Prerequisites

1. **AWS Bedrock Access**:
   ```bash
   # Option 1: Bedrock API Key (for development)
   export AWS_BEDROCK_API_KEY=your_bedrock_api_key
   
   # Option 2: AWS Credentials (for production)
   aws configure
   ```

2. **Enable Model Access**:
   - Open [Bedrock Console](https://console.aws.amazon.com/bedrock)
   - Navigate to "Model access" → "Manage model access"
   - Enable "Claude 4 Sonnet" (anthropic.claude-sonnet-4-20250514-v1:0)

3. **Install Dependencies**:
   ```bash
   npm install
   ```

### Running the Example

```bash
# Run the example script
npx ts-node Agents/examples/simple-calculator-example.ts
```

### Expected Output

```
=== Simple Calculator Agent Example ===

Agent created: SimpleCalculatorAgent
Description: A simple calculator agent that demonstrates Strands SDK integration
Capabilities: calculate, chat

---

Example 1: Simple Calculation
Request: Calculate 25 * 4 + 10
Response: The result of 25 * 4 + 10 is 110
Duration: 1523 ms
Costs: []

---

Example 2: Complex Calculation
Request: Calculate (100 + 50) / 3
Response: The result of (100 + 50) / 3 is 50
Duration: 1234 ms

---

Example 3: Mathematical Conversation
Request: What is the Pythagorean theorem?
Response: The Pythagorean theorem states that in a right triangle, 
the square of the hypotenuse equals the sum of squares of the other two sides...

---

Example 4: Using Conversation Context
Request: Can you calculate the hypotenuse of a triangle with sides 3 and 4?
Response: Using the Pythagorean theorem I just explained, 
the hypotenuse is sqrt(3² + 4²) = sqrt(9 + 16) = sqrt(25) = 5

---

Example 5: Direct Invocation
Request: What is 15% of 200?
Response: 15% of 200 is 30
MCP Calls: 0

---

Example 6: Health Check
Health Status: healthy
Timestamp: 2024-01-15T10:30:00.000Z
Details: { mcpAdapters: [] }

---

=== Examples Complete ===
```

## Code Walkthrough

### 1. Agent Initialization

```typescript
import { Agent as StrandsAgent, BedrockModel, tool } from '@strands-agents/sdk';
import { BaseAgent } from './BaseAgent.js';

export class SimpleCalculatorAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'SimpleCalculatorAgent',
            description: 'A simple calculator agent',
            capabilities: [...],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-sonnet-4-20250514-v1:0',
                region: 'us-west-2',
                temperature: 0.3,  // Lower for factual tasks
                maxTokens: 2048,
            },
            tools: [calculator],  // Register tools
        };

        super(config, mcpAdapters);
    }
}
```

**Key Points**:
- Extends `BaseAgent` which handles Strands SDK initialization
- Configures Bedrock model with appropriate parameters
- Registers tools that the agent can use
- Lower temperature (0.3) for factual calculations

### 2. Tool Definition

```typescript
@tool
function calculator(expression: string): string {
    /**
     * Evaluate a mathematical expression.
     * 
     * Args:
     *     expression: A mathematical expression to evaluate
     * 
     * Returns:
     *     The result of the calculation as a string
     */
    try {
        const result = eval(expression);
        return `The result of ${expression} is ${result}`;
    } catch (error) {
        return `Error: ${error.message}`;
    }
}
```

**Key Points**:
- Use `@tool` decorator to register the function
- Include detailed docstring - the model reads this
- Clear parameter descriptions help the model use the tool correctly
- Return descriptive strings, not just raw values

### 3. System Prompt

```typescript
protected getSystemPrompt(): string {
    return `You are a helpful calculator assistant. You can:
1. Perform mathematical calculations using the calculator tool
2. Explain mathematical concepts
3. Help users understand calculation results
4. Maintain conversation context

When a user asks you to calculate something, use the calculator tool.
Always explain your reasoning and show your work.`;
}
```

**Key Points**:
- Clear instructions on agent capabilities
- Explicit guidance on when to use tools
- Personality and tone definition
- Conversation behavior guidelines

### 4. Capability Execution

```typescript
async executeCapability(
    capability: string,
    parameters: Record<string, unknown>,
    context: AgentContext
): Promise<AgentResult> {
    if (capability === 'calculate') {
        const expression = parameters.expression as string;
        const prompt = `Please calculate: ${expression}`;
        return this.invoke(prompt, context);
    }
    
    return super.executeCapability(capability, parameters, context);
}
```

**Key Points**:
- Handle specific capabilities with custom logic
- Build appropriate prompts for the agent
- Fall back to base implementation for unknown capabilities
- Return structured `AgentResult` with success/error information

### 5. Agent Invocation

```typescript
// Create agent
const agent = new SimpleCalculatorAgent();

// Create context
const context: AgentContext = {
    executionId: 'test-001',
    planId: 'plan-001',
    stepId: 'step-001',
    environment: 'dev',
};

// Invoke agent
const result = await agent.executeCapability('calculate', {
    expression: '25 * 4 + 10'
}, context);

console.log(result.result);  // Agent's response
console.log(result.duration);  // Execution time
console.log(result.costs);  // Cost tracking
```

**Key Points**:
- Create agent instance once, reuse for multiple invocations
- Provide execution context for tracking and logging
- Handle both success and error cases
- Access performance metrics (duration, costs)

## Extending the Pattern

### Adding More Tools

```typescript
@tool
function getWeather(location: string): string {
    /**
     * Get weather information for a location.
     * 
     * Args:
     *     location: City name
     */
    return `Weather in ${location}: Sunny, 72°F`;
}

// Register in agent config
tools: [calculator, getWeather]
```

### Using Community Tools

```typescript
import { calculator, python_repl, http_request } from 'strands-agents-tools';

// Register community tools
tools: [calculator, python_repl, http_request]
```

### Adding MCP Adapters

```typescript
import { UnrealMCPAdapter } from '../MCP/adapters/UnrealMCPAdapter.js';

const unrealAdapter = new UnrealMCPAdapter(true); // mock mode
const agent = new SimpleCalculatorAgent([unrealAdapter]);

// Agent can now call MCP capabilities
const result = await agent.callMCP(
    'UnrealMCP',
    'build_project',
    { platform: 'Android' },
    context
);
```

### Customizing Model Configuration

```typescript
model: {
    provider: 'bedrock',
    modelId: 'anthropic.claude-sonnet-4-20250514-v1:0',
    region: 'us-west-2',
    temperature: 0.7,  // Higher for creative tasks
    maxTokens: 4096,   // More tokens for complex responses
}
```

## Best Practices

### 1. Temperature Settings
- **Factual tasks** (calculations, data retrieval): 0.1-0.3
- **Balanced tasks** (general conversation): 0.5-0.7
- **Creative tasks** (writing, brainstorming): 0.7-0.9

### 2. Tool Design
- Keep tools focused on single responsibilities
- Use clear, descriptive docstrings
- Return human-readable strings, not just data
- Handle errors gracefully within tools

### 3. System Prompts
- Be specific about agent capabilities
- Provide clear instructions on tool usage
- Define personality and tone
- Include examples for complex behaviors

### 4. Error Handling
- Always check `result.success` before using `result.result`
- Log errors with context for debugging
- Provide fallback behavior for failures
- Track error rates for monitoring

### 5. Cost Management
- Use lower max_tokens when possible
- Cache system prompts for repeated use
- Monitor cost tracking in results
- Set appropriate timeouts

## Troubleshooting

### "Access denied to model"
**Solution**: Enable model access in Bedrock console
1. Open [Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Model access → Manage model access
3. Enable Claude 4 Sonnet
4. Wait a few minutes for propagation

### "Invalid API key"
**Solution**: Check environment variable
```bash
echo $AWS_BEDROCK_API_KEY
# Should show your API key

# If empty, set it:
export AWS_BEDROCK_API_KEY=your_key
```

### "Tool not found"
**Solution**: Verify tool registration
- Check tool is in `tools` array in config
- Ensure `@tool` decorator is applied
- Verify tool function has proper docstring

### "Token limit exceeded"
**Solution**: Increase max_tokens
```typescript
model: {
    maxTokens: 4096,  // Increase from 2048
}
```

## Next Steps

1. **Study the Code**: Read through `SimpleCalculatorAgent.ts` with comments
2. **Run the Example**: Execute `simple-calculator-example.ts`
3. **Modify the Agent**: Add new capabilities or tools
4. **Create Your Own**: Use this as a template for new agents
5. **Integrate with System**: Connect to the Orchestrator for production use

## Additional Resources

- [Strands SDK Documentation](https://docs.strands.ai/)
- [BaseAgent Implementation](../BaseAgent.ts)
- [Agent Types](../types.ts)
- [MCP Adapters](../../MCP/README.md)
- [Orchestrator Integration](../../Orchestrator/README.md)

This simple calculator agent demonstrates all the core patterns needed to build production agents with Strands SDK integration.