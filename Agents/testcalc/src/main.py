"""
Simple Calculator Agent with Claude 3.7 Sonnet
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Tool: Simple calculator
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error: {str(e)}"


@app.entrypoint
async def invoke(payload, context):
    """AgentCore entrypoint"""
    
    try:
        # Use Claude 3.7 Sonnet
        model = BedrockModel(
            model_id="anthropic.claude-3-7-sonnet-20250219-v1:0"
        )
        
        # Create agent inside handler
        agent = Agent(
            model=model,
            tools=[calculator],
            system_prompt="You are a calculator assistant. Use the calculator tool to evaluate math expressions."
        )
        
        # Get prompt from payload
        prompt = payload.get('prompt', '')
        
        if not prompt:
            yield json.dumps({'error': 'No prompt provided'})
            return
        
        # Stream response
        stream = agent.stream_async(prompt)
        
        async for event in stream:
            if "data" in event and isinstance(event["data"], str):
                yield event["data"]
                
    except Exception as e:
        yield json.dumps({'error': f'Agent error: {str(e)}'})
