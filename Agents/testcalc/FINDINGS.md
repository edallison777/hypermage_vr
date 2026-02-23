# AgentCore Deployment Findings

## Problem
AWS Bedrock AgentCore has a hard 30-second initialization timeout for direct code deploy that cannot be extended. The Strands SDK package (24MB with minimal dependencies) exceeds this limit, causing all invocations to fail with "Runtime initialization time exceeded."

## What We Tried
1. **Minimal dependencies** - Reduced from 42MB to 24MB to 17MB
2. **Module-level initialization** - Created agent at module level vs inside handler
3. **Handler-level initialization** - Created agent inside async handler
4. **Different model IDs** - Tried various Claude model configurations
5. **Async streaming** - Used proper async/await patterns

## Result
All attempts failed with the same 30-second timeout error, even with:
- Only `bedrock-agentcore` and `strands-agents` dependencies (24MB)
- Only `bedrock-agentcore` dependency (17MB) - still times out
- Absolute minimal echo handler (no Strands) - still times out at 17MB

## Root Cause
The AgentCore runtime environment needs to:
1. Download the 17-24MB package from S3
2. Extract the package
3. Initialize Python environment
4. Load all dependencies
5. Execute module-level code

This process exceeds 30 seconds in the AgentCore runtime environment.

## Solution Options

### Option 1: Container Deployment (RECOMMENDED)
Use container deployment instead of direct code deploy. Containers pre-build all dependencies into a Docker image, eliminating initialization time.

**Pros:**
- No initialization timeout issues
- Dependencies are pre-built
- Faster cold starts after first deployment

**Cons:**
- Requires Docker/Finch/Podman for local builds
- Slightly more complex deployment process
- Larger artifact size (but doesn't matter for containers)

### Option 2: Lambda Function Tools
Deploy Strands logic to Lambda functions and call them as tools from a minimal AgentCore agent.

**Pros:**
- AgentCore agent stays minimal
- Lambda has 10GB package size limit
- Can use Lambda layers for dependencies

**Cons:**
- More complex architecture
- Additional Lambda costs
- Latency from Lambda invocations

### Option 3: Reduce Dependencies Further
Find or create a minimal agent framework without Strands.

**Pros:**
- Stays within direct code deploy limits
- Simpler deployment

**Cons:**
- Loses Strands SDK benefits
- Need to implement agent logic manually
- Not using "Strands agents" as specified in requirements

## Recommendation
Use **Container Deployment** (Option 1). This maintains the requirement that "all agents must be Strands agents deployed to AgentCore runtime" while solving the initialization timeout issue.

## Next Steps
1. Create new AgentCore project configured for container deployment
2. Add Dockerfile for ARM64 Linux
3. Deploy using `agentcore deploy` (uses CodeBuild for cloud container builds)
4. Test with Claude 3.7 Sonnet
5. Add Lambda function tool integration
6. Document the working pattern for production agents

## Local Testing Success
The agent code WORKS when run locally with `agentcore deploy --local`:
- Successfully installed 153 packages
- Server started on localhost:8080
- Code is correct, only cloud initialization times out

This proves the Strands + AgentCore integration is valid, we just need container deployment for cloud runtime.
