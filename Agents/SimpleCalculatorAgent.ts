/**
 * Simple Calculator Agent - Strands SDK Example
 * 
 * This is a minimal example agent that demonstrates proper Strands SDK integration.
 * It provides basic calculator functionality and serves as a template for building
 * more complex agents.
 * 
 * Key Features:
 * - Proper Strands Agent SDK initialization
 * - Tool integration (calculator tool)
 * - Conversation context management
 * - Error handling
 * - Cost tracking
 * 
 * This agent can be used as a reference for understanding how to:
 * 1. Initialize a Strands agent with Bedrock
 * 2. Define and use tools
 * 3. Handle agent invocations
 * 4. Maintain conversation history
 */

import { Agent as StrandsAgent, BedrockModel, tool } from '@strands-agents/sdk';
import { BaseAgent } from './BaseAgent.js';
import type {
    AgentConfig,
    AgentCapability,
    AgentContext,
    AgentResult,
} from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

/**
 * Calculator tool for the agent
 * Demonstrates how to create a simple tool that the agent can use
 */
@tool
function calculator(expression: string): string {
    /**
     * Evaluate a mathematical expression.
     * 
     * Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")
     * 
     * Returns:
     *     The result of the calculation as a string
     */
    try {
        // Simple evaluation (in production, use a safe math parser)
        const result = eval(expression);
        return `The result of ${expression} is ${result}`;
    } catch (error) {
        return `Error evaluating expression: ${error instanceof Error ? error.message : String(error)}`;
    }
}

/**
 * Simple Calculator Agent
 * 
 * A minimal agent that can perform basic calculations and maintain conversation context.
 * This serves as a reference implementation for Strands SDK integration.
 */
export class SimpleCalculatorAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'SimpleCalculatorAgent',
            description: 'A simple calculator agent that demonstrates Strands SDK integration',
            capabilities: [
                {
                    name: 'calculate',
                    description: 'Perform mathematical calculations',
                    parameters: {
                        type: 'object',
                        properties: {
                            expression: {
                                type: 'string',
                                description: 'Mathematical expression to evaluate',
                            },
                        },
                        required: ['expression'],
                    },
                    estimatedCost: 0.01,
                    estimatedDuration: 1000,
                },
                {
                    name: 'chat',
                    description: 'Have a conversation about mathematics',
                    parameters: {
                        type: 'object',
                        properties: {
                            message: {
                                type: 'string',
                                description: 'Message to send to the agent',
                            },
                        },
                        required: ['message'],
                    },
                    estimatedCost: 0.01,
                    estimatedDuration: 2000,
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-sonnet-4-20250514-v1:0',
                region: 'us-west-2',
                temperature: 0.3, // Lower temperature for factual calculations
                maxTokens: 2048,
            },
            tools: [calculator], // Register the calculator tool
        };

        super(config, mcpAdapters);
    }

    /**
     * Get the system prompt for this agent
     * This defines the agent's personality and capabilities
     */
    protected getSystemPrompt(): string {
        return `You are a helpful calculator assistant. You can:
1. Perform mathematical calculations using the calculator tool
2. Explain mathematical concepts
3. Help users understand calculation results
4. Maintain conversation context to remember previous calculations

When a user asks you to calculate something, use the calculator tool.
Always explain your reasoning and show your work.
Be friendly and educational in your responses.`;
    }

    /**
     * Execute the 'calculate' capability
     * This demonstrates how to handle a specific capability
     */
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

        if (capability === 'chat') {
            const message = parameters.message as string;
            return this.invoke(message, context);
        }

        // Fall back to base implementation for unknown capabilities
        return super.executeCapability(capability, parameters, context);
    }
}

/**
 * Example usage:
 * 
 * ```typescript
 * import { SimpleCalculatorAgent } from './SimpleCalculatorAgent.js';
 * 
 * // Create the agent
 * const agent = new SimpleCalculatorAgent();
 * 
 * // Create execution context
 * const context = {
 *     executionId: 'test-001',
 *     planId: 'plan-001',
 *     stepId: 'step-001',
 *     environment: 'dev',
 * };
 * 
 * // Use the calculate capability
 * const result1 = await agent.executeCapability('calculate', {
 *     expression: '25 * 4 + 10'
 * }, context);
 * console.log(result1.result);
 * 
 * // Have a conversation
 * const result2 = await agent.executeCapability('chat', {
 *     message: 'What is the Pythagorean theorem?'
 * }, context);
 * console.log(result2.result);
 * 
 * // The agent maintains conversation context
 * const result3 = await agent.executeCapability('chat', {
 *     message: 'Can you calculate the hypotenuse of a triangle with sides 3 and 4?'
 * }, context);
 * console.log(result3.result);
 * ```
 */
