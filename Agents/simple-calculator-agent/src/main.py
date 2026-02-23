"""
Simple Calculator Agent - AgentCore Deployment Example

This agent demonstrates:
1. Strands SDK integration with Claude via Bedrock
2. Tool calling (calculator and Lambda invocation)
3. Proper AgentCore deployment patterns

This is a proof-of-concept for the larger Unreal VR Multiplayer System.
"""

import json
import boto3
from strands import Agent, tool
from bedrock_agentcore import BedrockAgentCoreApp

# Tool 1: Simple calculator
@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.
    
    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")
    
    Returns:
        The result of the calculation as a string
    """
    try:
        # Simple evaluation (in production, use a safe math parser)
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"


# Tool 2: Lambda function invoker
@tool
def invoke_add_numbers_lambda(a: int, b: int) -> str:
    """
    Invoke the add_numbers Lambda function to add two numbers.
    
    This demonstrates calling AWS Lambda functions from an agent.
    
    Args:
        a: First number to add
        b: Second number to add
    
    Returns:
        The sum of the two numbers
    """
    try:
        lambda_client = boto3.client('lambda')
        
        payload = {
            'a': a,
            'b': b
        }
        
        response = lambda_client.invoke(
            FunctionName='simple-calculator-add-numbers',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        return f"Lambda function returned: {result['result']}"
        
    except Exception as e:
        return f"Error invoking Lambda: {str(e)}"


# Create the Strands agent
agent = Agent(
    tools=[calculator, invoke_add_numbers_lambda],
    system_prompt="""You are a helpful calculator assistant deployed on AWS Bedrock AgentCore.

You have two capabilities:
1. Calculate mathematical expressions using the calculator tool
2. Add two numbers using the add_numbers Lambda function

When a user asks you to calculate something:
- Use the calculator tool for general math expressions
- Use the Lambda function when specifically asked to use it or for simple addition

Always explain your reasoning and show your work.
Be friendly and educational in your responses.

This is a proof-of-concept agent for the Unreal VR Multiplayer System project."""
)

# Wrap the agent for AgentCore deployment
app = BedrockAgentCoreApp(agent=agent)


@app.entrypoint
def handler(event, context):
    """
    AgentCore entrypoint handler.
    
    This function is called by AgentCore Runtime when the agent is invoked.
    
    Args:
        event: Event payload containing the prompt
        context: Lambda context (provided by AgentCore)
    
    Returns:
        Response dictionary with the agent's answer
    """
    # Extract prompt from event
    prompt = event.get('prompt', '')
    
    if not prompt:
        return {
            'error': 'No prompt provided',
            'usage': 'Send a JSON payload with a "prompt" field'
        }
    
    # Invoke the agent
    try:
        response = agent(prompt)
        return {
            'response': response,
            'status': 'success'
        }
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error'
        }
