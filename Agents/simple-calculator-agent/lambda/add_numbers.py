"""
Simple Lambda function for adding two numbers.

This demonstrates a Lambda function that can be called by the AgentCore agent.
"""

def lambda_handler(event, context):
    """
    Add two numbers together.
    
    Args:
        event: Event payload with 'a' and 'b' fields
        context: Lambda context
    
    Returns:
        Dictionary with the result
    """
    a = event.get('a', 0)
    b = event.get('b', 0)
    
    result = a + b
    
    return {
        'statusCode': 200,
        'result': result,
        'operation': 'addition',
        'inputs': {'a': a, 'b': b}
    }
