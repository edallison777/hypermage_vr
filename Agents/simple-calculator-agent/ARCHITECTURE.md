# Architecture: Simple Calculator Agent

## Overview

This is a proof-of-concept Strands agent deployed to AWS Bedrock AgentCore Runtime. It demonstrates the foundational patterns that will be used for all agents in the Unreal VR Multiplayer System.

## Key Architectural Decisions

### 1. AgentCore Runtime (NOT Bedrock Inference)

**What we're using:**
- AWS Bedrock AgentCore Runtime - a managed serverless platform for hosting agents
- Agents are deployed as containerized applications
- AgentCore handles scaling, monitoring, and lifecycle management

**What we're NOT using:**
- Direct Bedrock inference API calls
- Self-managed EC2 or ECS deployments
- Lambda functions for agent hosting (Lambda is only for tools)

### 2. Strands SDK Integration

**Agent Framework:**
```python
from strands import Agent, tool

agent = Agent(
    tools=[calculator, invoke_lambda],
    system_prompt="..."
)
```

**Key Features:**
- Foundation model abstraction (Claude via Bedrock)
- Tool calling with `@tool` decorator
- Conversation context management
- Automatic prompt engineering

### 3. AgentCore Deployment Pattern

**Wrapping Pattern:**
```python
from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp(agent=agent)

@app.entrypoint
def handler(event, context):
    prompt = event.get('prompt', '')
    response = agent(prompt)
    return {'response': response}
```

**This pattern:**
- Wraps the Strands agent for AgentCore compatibility
- Provides the entrypoint that AgentCore invokes
- Handles event parsing and response formatting

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Bedrock AgentCore                     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  AgentCore Runtime (Serverless Container)              │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Strands Agent                                    │  │ │
│  │  │  - Foundation Model: Claude 4 Sonnet (Bedrock)   │  │ │
│  │  │  - System Prompt: Calculator assistant           │  │ │
│  │  │  - Tools: [calculator, invoke_lambda]            │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  BedrockAgentCoreApp Wrapper                     │  │ │
│  │  │  - Entrypoint handler                            │  │ │
│  │  │  - Event parsing                                 │  │ │
│  │  │  - Response formatting                           │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│                          │ boto3.client('lambda').invoke()  │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  AWS Lambda Function                                   │ │
│  │  - Function: simple-calculator-add-numbers            │ │
│  │  - Runtime: Python 3.12                               │ │
│  │  - Handler: add_numbers.lambda_handler                │ │
│  │  - Operation: Addition (a + b)                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Agent Invocation

```
User/Orchestrator
    │
    │ HTTP POST /invocations
    │ {"prompt": "Calculate 5 + 3"}
    ▼
AgentCore Runtime
    │
    │ Invoke entrypoint
    ▼
handler(event, context)
    │
    │ Extract prompt
    ▼
agent(prompt)
    │
    │ Claude processes prompt
    │ Decides to use calculator tool
    ▼
@tool calculator(expression)
    │
    │ eval("5 + 3")
    ▼
Return "The result of 5 + 3 is 8"
    │
    ▼
Return {"response": "...", "status": "success"}
```

### 2. Lambda Tool Invocation

```
User/Orchestrator
    │
    │ {"prompt": "Use Lambda to add 10 and 20"}
    ▼
AgentCore Runtime → agent(prompt)
    │
    │ Claude decides to use invoke_add_numbers_lambda
    ▼
@tool invoke_add_numbers_lambda(a=10, b=20)
    │
    │ boto3.client('lambda').invoke()
    ▼
Lambda Function: add_numbers
    │
    │ a + b = 30
    ▼
Return {"result": 30}
    │
    ▼
Return "Lambda function returned: 30"
```

## Development Workflow

### Local Development

```bash
# Terminal 1: Dev server with hot reload
agentcore dev

# Terminal 2: Test invocations
agentcore invoke --dev '{"prompt": "test"}'
```

**What happens:**
1. `agentcore dev` starts uvicorn server on localhost:8080
2. Watches `src/main.py` for changes
3. Auto-reloads on file save
4. `agentcore invoke --dev` sends HTTP POST to localhost

### Cloud Deployment

```bash
agentcore launch
```

**What happens:**
1. Packages agent code and dependencies
2. Creates Docker container image
3. Pushes to ECR (Elastic Container Registry)
4. Deploys to AgentCore Runtime
5. Configures IAM roles and permissions
6. Returns agent endpoint URL

## Configuration Files

### .bedrock_agentcore.yaml

```yaml
entrypoint: src/main.py        # Python file with @app.entrypoint
agent_name: simple-calculator-agent
runtime: python3.12
memory:
  mode: NO_MEMORY              # Start without memory for simplicity
model:
  provider: bedrock
  model_id: anthropic.claude-sonnet-4-20250514-v1:0
  region: eu-west-1
```

### requirements.txt

```
bedrock-agentcore              # AgentCore SDK
strands-agents                 # Strands SDK
strands-agents-tools           # Community tools
boto3                          # AWS SDK for Lambda invocation
```

## Tool Patterns

### Pattern 1: Pure Python Tool

```python
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    result = eval(expression)
    return f"Result: {result}"
```

**Characteristics:**
- No external dependencies
- Fast execution
- Runs in agent process

### Pattern 2: AWS Service Tool

```python
@tool
def invoke_add_numbers_lambda(a: int, b: int) -> str:
    """Invoke Lambda function to add numbers."""
    lambda_client = boto3.client('lambda')
    response = lambda_client.invoke(
        FunctionName='simple-calculator-add-numbers',
        Payload=json.dumps({'a': a, 'b': b})
    )
    return json.loads(response['Payload'].read())
```

**Characteristics:**
- Calls external AWS service
- Requires IAM permissions
- Network latency
- Demonstrates service integration

## Scaling to Production Agents

This simple agent demonstrates patterns that will be used in production agents:

### ProducerOrchestratorAgent
- **Tools:** DynamoDB queries, S3 operations, agent coordination
- **Model:** Claude 4 Sonnet (reasoning-heavy)
- **Memory:** STM_AND_LTM for project context

### ConversationLevelDesignerAgent
- **Tools:** JSON schema validation, geometry calculations
- **Model:** Claude 4 Sonnet (creative design)
- **Memory:** STM_ONLY for conversation context

### CostMonitorFinOpsAgent
- **Tools:** CloudWatch metrics, Cost Explorer API
- **Model:** Claude 4 Sonnet (analytical)
- **Memory:** NO_MEMORY (stateless cost checks)

### DevOpsAWSAgent
- **Tools:** Terraform execution, CloudFormation, CodePipeline
- **Model:** Claude 4 Sonnet (infrastructure reasoning)
- **Memory:** STM_ONLY for deployment context

## Security Considerations

### IAM Permissions

**AgentCore Runtime needs:**
- `bedrock:InvokeModel` - Call foundation models
- `lambda:InvokeFunction` - Call Lambda tools
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` - Logging

**Lambda Function needs:**
- `logs:*` - CloudWatch logging
- (No other permissions for simple addition)

### Network Security

- AgentCore Runtime runs in AWS-managed VPC
- Lambda functions can be in private subnets
- No public internet access required
- All communication via AWS PrivateLink

## Cost Optimization

### AgentCore Runtime
- Serverless - pay per invocation
- Auto-scales to zero when idle
- No minimum charges

### Foundation Model
- Claude 4 Sonnet: $3/1M input tokens, $15/1M output tokens
- Use caching for repeated prompts (not implemented in POC)
- Consider Claude 3.5 Sonnet for cost savings

### Lambda
- Free tier: 1M requests/month
- Minimal compute time for simple operations
- Consider Lambda SnapStart for faster cold starts

## Monitoring and Observability

### AgentCore Observability (Future)
- Request/response logging
- Token usage tracking
- Tool invocation metrics
- Error rates and latency

### CloudWatch Integration
- Agent logs: `/aws/agentcore/simple-calculator-agent`
- Lambda logs: `/aws/lambda/simple-calculator-add-numbers`
- Custom metrics for business logic

## Next Steps

1. **Add AgentCore Memory** - Enable conversation history
2. **Add AgentCore Gateway** - Expose MCP tools
3. **Add more tools** - DynamoDB, S3, API calls
4. **Implement production agents** - Use this pattern for all 10 agents
5. **Add observability** - Metrics, traces, logs
6. **Add testing** - Unit tests, integration tests, property-based tests

## References

- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands SDK Documentation](https://docs.strands.ai/)
- [Bedrock Model Access](https://console.aws.amazon.com/bedrock)
- [AgentCore CLI Reference](https://github.com/awslabs/bedrock-agentcore-starter-toolkit)
