/**
 * Simple Calculator Agent Example
 * 
 * This example demonstrates how to use the SimpleCalculatorAgent
 * with proper Strands SDK integration.
 */

import { SimpleCalculatorAgent } from '../SimpleCalculatorAgent.js';
import type { AgentContext } from '../types.js';

async function main() {
    console.log('=== Simple Calculator Agent Example ===\n');

    // Create the agent
    const agent = new SimpleCalculatorAgent();

    // Create execution context
    const context: AgentContext = {
        executionId: 'example-001',
        planId: 'plan-001',
        stepId: 'step-001',
        environment: 'dev',
    };

    console.log('Agent created:', agent.getName());
    console.log('Description:', agent.getDescription());
    console.log('Capabilities:', agent.getCapabilities().map(c => c.name).join(', '));
    console.log('\n---\n');

    // Example 1: Simple calculation
    console.log('Example 1: Simple Calculation');
    console.log('Request: Calculate 25 * 4 + 10');
    const result1 = await agent.executeCapability('calculate', {
        expression: '25 * 4 + 10'
    }, context);

    if (result1.success) {
        console.log('Response:', result1.result);
        console.log('Duration:', result1.duration, 'ms');
        console.log('Costs:', result1.costs);
    } else {
        console.error('Error:', result1.error);
    }
    console.log('\n---\n');

    // Example 2: Complex calculation
    console.log('Example 2: Complex Calculation');
    console.log('Request: Calculate (100 + 50) / 3');
    const result2 = await agent.executeCapability('calculate', {
        expression: '(100 + 50) / 3'
    }, context);

    if (result2.success) {
        console.log('Response:', result2.result);
        console.log('Duration:', result2.duration, 'ms');
    } else {
        console.error('Error:', result2.error);
    }
    console.log('\n---\n');

    // Example 3: Conversation about mathematics
    console.log('Example 3: Mathematical Conversation');
    console.log('Request: What is the Pythagorean theorem?');
    const result3 = await agent.executeCapability('chat', {
        message: 'What is the Pythagorean theorem?'
    }, context);

    if (result3.success) {
        console.log('Response:', result3.result);
    } else {
        console.error('Error:', result3.error);
    }
    console.log('\n---\n');

    // Example 4: Using conversation context
    console.log('Example 4: Using Conversation Context');
    console.log('Request: Can you calculate the hypotenuse of a triangle with sides 3 and 4?');
    const result4 = await agent.executeCapability('chat', {
        message: 'Can you calculate the hypotenuse of a triangle with sides 3 and 4?'
    }, context);

    if (result4.success) {
        console.log('Response:', result4.result);
    } else {
        console.error('Error:', result4.error);
    }
    console.log('\n---\n');

    // Example 5: Direct invocation (alternative to executeCapability)
    console.log('Example 5: Direct Invocation');
    console.log('Request: What is 15% of 200?');
    const result5 = await agent.invoke('What is 15% of 200?', context);

    if (result5.success) {
        console.log('Response:', result5.result);
        console.log('MCP Calls:', result5.mcpCalls?.length || 0);
    } else {
        console.error('Error:', result5.error);
    }
    console.log('\n---\n');

    // Example 6: Health check
    console.log('Example 6: Health Check');
    const health = await agent.getHealth();
    console.log('Health Status:', health.status);
    console.log('Timestamp:', health.timestamp);
    console.log('Details:', health.details);
    console.log('\n---\n');

    console.log('=== Examples Complete ===');
}

// Run the examples
main().catch(console.error);

/**
 * Expected Output:
 * 
 * The agent will:
 * 1. Perform calculations using the calculator tool
 * 2. Explain mathematical concepts
 * 3. Maintain conversation context across multiple interactions
 * 4. Track costs and duration for each operation
 * 5. Provide health status information
 * 
 * To run this example:
 * 
 * 1. Ensure you have AWS Bedrock credentials configured:
 *    export AWS_BEDROCK_API_KEY=your_key
 *    OR
 *    aws configure
 * 
 * 2. Enable Claude 4 Sonnet model access in Bedrock console
 * 
 * 3. Install dependencies:
 *    npm install
 * 
 * 4. Run the example:
 *    npx ts-node Agents/examples/simple-calculator-example.ts
 */
