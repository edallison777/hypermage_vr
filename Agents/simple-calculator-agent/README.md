# Simple Calculator Agent - AgentCore Deployment

This is a minimal Strands agent deployed to AWS Bedrock AgentCore Runtime that demonstrates:
- Foundation model integration (Claude via Bedrock)
- Lambda function tool calling
- Proper AgentCore deployment patterns

## Architecture

```
┌─────────────────────────────────────────┐
│   AgentCore Runtime (Serverless)        │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Strands Agent                     │ │
│  │  - Claude 4 Sonnet (Bedrock)       │ │
│  │  - Calculator tool                 │ │
│  │  - Lambda invoker tool             │ │
│  └────────────────────────────────────┘ │
│              │                           │
│              ▼                           │
│  ┌────────────────────────────────────┐ │
│  │  Lambda Function                   │ │
│  │  - Simple addition operation       │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Prerequisites

1. Install AgentCore toolkit:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```

2. Install Strands SDK:
   ```bash
   pip install strands-agents strands-agents-tools
   ```

3. AWS credentials configured:
   ```bash
   aws configure
   ```

4. Enable Claude 4 Sonnet in Bedrock console

## Project Structure

```
simple-calculator-agent/
├── src/
│   └── main.py              # Agent entrypoint
├── lambda/
│   └── add_numbers.py       # Lambda function code
├── infra/
│   └── lambda.tf            # Terraform for Lambda
├── requirements.txt         # Python dependencies
├── .bedrock_agentcore.yaml  # AgentCore configuration
└── README.md                # This file
```

## Local Development

1. **Start the dev server:**
   ```bash
   cd Agents/simple-calculator-agent
   agentcore dev
   ```

2. **Test locally (in another terminal):**
   ```bash
   # Simple calculation
   agentcore invoke --dev '{"prompt": "Calculate 5 + 3"}'
   
   # Lambda invocation
   agentcore invoke --dev '{"prompt": "Use the Lambda function to add 10 and 20"}'
   ```

## Deployment

1. **Deploy Lambda function first:**
   ```bash
   cd infra
   terraform init
   terraform apply
   ```

2. **Configure AgentCore:**
   ```bash
   cd ..
   agentcore configure --entrypoint src/main.py --non-interactive
   ```

3. **Deploy to AgentCore:**
   ```bash
   agentcore launch
   ```

4. **Test deployed agent:**
   ```bash
   agentcore invoke '{"prompt": "Calculate 15 * 4"}'
   ```

## Agent Capabilities

### 1. Calculator Tool
Built-in Python calculator for basic math operations.

**Example:**
```bash
agentcore invoke '{"prompt": "What is 25 * 4 + 10?"}'
```

### 2. Lambda Function Tool
Invokes a Lambda function to perform addition.

**Example:**
```bash
agentcore invoke '{"prompt": "Use the add_numbers Lambda to add 100 and 50"}'
```

## Code Walkthrough

### Agent Definition (src/main.py)

```python
from strands import Agent, tool
from bedrock_agentcore import BedrockAgentCoreApp
import boto3

# Define calculator tool
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    result = eval(expression)
    return f"Result: {result}"

# Define Lambda invoker tool
@tool
def invoke_lambda(function_name: str, payload: dict) -> str:
    """Invoke an AWS Lambda function."""
    lambda_client = boto3.client('lambda')
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    return json.loads(response['Payload'].read())

# Create Strands agent
agent = Agent(
    tools=[calculator, invoke_lambda],
    system_prompt="You are a calculator assistant..."
)

# Wrap for AgentCore deployment
app = BedrockAgentCoreApp(agent=agent)

@app.entrypoint
def handler(event, context):
    prompt = event.get('prompt', '')
    response = agent(prompt)
    return {'response': response}
```

### Lambda Function (lambda/add_numbers.py)

```python
def lambda_handler(event, context):
    a = event.get('a', 0)
    b = event.get('b', 0)
    return {'result': a + b}
```

## Key Patterns

### 1. Tool Definition
Use `@tool` decorator with clear docstrings:
```python
@tool
def my_tool(param: str) -> str:
    """Tool description that the model reads."""
    return result
```

### 2. AgentCore Wrapping
Wrap your agent with `BedrockAgentCoreApp`:
```python
app = BedrockAgentCoreApp(agent=agent)

@app.entrypoint
def handler(event, context):
    # Your handler logic
    pass
```

### 3. Lambda Integration
Use boto3 to invoke Lambda functions:
```python
lambda_client = boto3.client('lambda')
response = lambda_client.invoke(
    FunctionName='my-function',
    Payload=json.dumps(payload)
)
```

## Troubleshooting

### Dev server won't start
- Check `src/main.py` exists
- Verify syntax: `python -m py_compile src/main.py`
- Ensure dependencies installed: `pip install -r requirements.txt`

### Lambda invocation fails
- Verify Lambda function is deployed
- Check IAM permissions for Lambda invoke
- Ensure function name is correct

### Deployment fails
- Run `aws sts get-caller-identity` to verify AWS credentials
- Check Bedrock model access in AWS console
- Verify `.bedrock_agentcore.yaml` configuration

## Cost Considerations

- **AgentCore Runtime:** Serverless, pay per invocation
- **Claude 4 Sonnet:** ~$3 per 1M input tokens, ~$15 per 1M output tokens
- **Lambda:** $0.20 per 1M requests + compute time

## Next Steps

1. Add more tools (API calls, database queries, etc.)
2. Integrate AgentCore Memory for conversation history
3. Add AgentCore Gateway for MCP tool integration
4. Deploy to production with proper IAM roles
5. Add monitoring and observability

## References

- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands SDK Documentation](https://docs.strands.ai/)
- [Bedrock Model Access](https://console.aws.amazon.com/bedrock)
