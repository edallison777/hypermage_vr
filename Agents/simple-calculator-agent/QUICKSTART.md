# Quick Start Guide

This guide will get you from zero to a deployed AgentCore agent in minutes.

## Step 1: Install Prerequisites

```bash
# Install AgentCore toolkit
pip install bedrock-agentcore-starter-toolkit

# Install Strands SDK
pip install strands-agents strands-agents-tools boto3

# Verify AWS credentials
aws sts get-caller-identity
```

## Step 2: Enable Bedrock Model Access

1. Open [Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to "Model access" → "Manage model access"
3. Enable "Claude 4 Sonnet" (anthropic.claude-sonnet-4-20250514-v1:0)
4. Wait a few minutes for access to propagate

## Step 3: Deploy Lambda Function

```bash
cd Agents/simple-calculator-agent/infra
terraform init
terraform apply
# Type 'yes' when prompted
```

This creates the `simple-calculator-add-numbers` Lambda function.

## Step 4: Test Locally

```bash
cd ..  # Back to simple-calculator-agent directory

# Terminal 1: Start dev server
agentcore dev

# Terminal 2: Test the agent
agentcore invoke --dev '{"prompt": "Calculate 5 + 3"}'
agentcore invoke --dev '{"prompt": "What is 25 * 4?"}'
agentcore invoke --dev '{"prompt": "Use the Lambda function to add 10 and 20"}'
```

## Step 5: Deploy to AgentCore

```bash
# Deploy to AWS
agentcore launch

# Test deployed agent
agentcore invoke '{"prompt": "Calculate 15 * 4"}'
agentcore invoke '{"prompt": "Use the add_numbers Lambda to add 100 and 50"}'
```

## Step 6: Check Status

```bash
# View deployment status
agentcore status

# View logs
agentcore logs
```

## Step 7: Clean Up (When Done)

```bash
# Preview what will be destroyed
agentcore destroy --dry-run

# Destroy AgentCore resources
agentcore destroy

# Destroy Lambda function
cd infra
terraform destroy
```

## Troubleshooting

### "Access denied to model"
- Enable Claude 4 Sonnet in Bedrock console
- Wait 5 minutes for propagation
- Verify with: `aws bedrock list-foundation-models --region eu-west-1`

### "Lambda function not found"
- Verify Lambda is deployed: `aws lambda get-function --function-name simple-calculator-add-numbers`
- Check region matches (eu-west-1)
- Redeploy with `terraform apply`

### "Dev server won't start"
- Check Python version: `python --version` (need 3.12+)
- Install dependencies: `pip install -r requirements.txt`
- Verify file exists: `ls src/main.py`

### "AgentCore launch fails"
- Check AWS credentials: `aws sts get-caller-identity`
- Verify region: `aws configure get region`
- Check IAM permissions for AgentCore

## What's Next?

Now that you have a working AgentCore agent, you can:

1. **Add more tools** - Create additional `@tool` functions
2. **Integrate Memory** - Add conversation history with AgentCore Memory
3. **Add Gateway** - Expose MCP tools via AgentCore Gateway
4. **Scale up** - Deploy the full production agents for the Unreal VR system

## Key Files

- `src/main.py` - Agent code with tools and entrypoint
- `lambda/add_numbers.py` - Lambda function code
- `.bedrock_agentcore.yaml` - AgentCore configuration
- `requirements.txt` - Python dependencies
- `infra/lambda.tf` - Terraform for Lambda

## Commands Reference

```bash
# Local development
agentcore dev                                    # Start dev server
agentcore invoke --dev '{"prompt": "..."}'      # Test locally

# Deployment
agentcore configure --entrypoint src/main.py    # Configure (if needed)
agentcore launch                                 # Deploy to AWS
agentcore status                                 # Check status
agentcore invoke '{"prompt": "..."}'            # Test deployed agent

# Cleanup
agentcore stop-session                           # Stop active session
agentcore destroy --dry-run                      # Preview destruction
agentcore destroy                                # Destroy resources
```

## Cost Estimate

- **AgentCore Runtime:** ~$0.0001 per invocation
- **Claude 4 Sonnet:** ~$3 per 1M input tokens, ~$15 per 1M output tokens
- **Lambda:** $0.20 per 1M requests + $0.0000166667 per GB-second

**Example:** 1000 agent invocations with average 500 tokens = ~$0.10 + $0.02 = $0.12

## Support

- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands SDK Documentation](https://docs.strands.ai/)
- [Project README](./README.md)
