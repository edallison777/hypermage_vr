/**
 * Base Agent class using Strands SDK
 * 
 * All specialized agents extend this base class which provides:
 * - Strands Agent SDK integration
 * - MCP adapter communication
 * - Cost tracking
 * - Error handling and retries
 * - Provenance logging
 */

import { Agent as StrandsAgent, BedrockModel } from '@strands-agents/sdk';
import type {
    IAgent,
    AgentConfig,
    AgentCapability,
    AgentContext,
    AgentResult,
    AgentHealthStatus,
    AgentError,
    MCPCallRecord,
    AgentCostRecord,
} from './types.js';
import type { IMCPAdapter, MCPRequest, MCPResponse } from '../MCP/types.js';

export abstract class BaseAgent implements IAgent {
    protected config: AgentConfig;
    protected strandsAgent: StrandsAgent;
    protected mcpAdapters: Map<string, IMCPAdapter>;
    protected mcpCallHistory: MCPCallRecord[];
    protected costHistory: AgentCostRecord[];

    constructor(config: AgentConfig, mcpAdapters: IMCPAdapter[] = []) {
        this.config = config;
        this.mcpAdapters = new Map();
        this.mcpCallHistory = [];
        this.costHistory = [];

        // Register MCP adapters
        for (const adapter of mcpAdapters) {
            this.mcpAdapters.set(adapter.getName(), adapter);
        }

        // Initialize Strands Agent with model configuration
        const modelConfig = config.model || {
            provider: 'bedrock',
            modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
            region: 'eu-west-1',
        };

        let model;
        switch (modelConfig.provider) {
            case 'bedrock':
                model = new BedrockModel({
                    region: modelConfig.region || 'eu-west-1',
                    modelId: modelConfig.modelId,
                    temperature: modelConfig.temperature,
                    maxTokens: modelConfig.maxTokens,
                });
                break;
            // Add other providers as needed
            default:
                throw new Error(`Unsupported model provider: ${modelConfig.provider}`);
        }

        this.strandsAgent = new StrandsAgent({
            model,
            tools: (config.tools || []) as any,
            systemPrompt: this.getSystemPrompt(),
        });
    }

    /**
     * Get the system prompt for this agent
     * Subclasses should override to provide agent-specific instructions
     */
    protected abstract getSystemPrompt(): string;

    /**
     * Get agent name
     */
    getName(): string {
        return this.config.name;
    }

    /**
     * Get agent description
     */
    getDescription(): string {
        return this.config.description;
    }

    /**
     * Get list of capabilities
     */
    getCapabilities(): AgentCapability[] {
        return this.config.capabilities;
    }

    /**
     * Invoke the agent with a natural language prompt
     */
    async invoke(prompt: string, context: AgentContext): Promise<AgentResult> {
        const startTime = Date.now();

        try {
            // Build context-aware prompt
            const fullPrompt = this.buildContextualPrompt(prompt, context);

            // Invoke Strands agent
            const result = await this.strandsAgent.invoke(fullPrompt);

            const duration = Date.now() - startTime;

            return {
                success: true,
                result: result.lastMessage,
                duration,
                mcpCalls: [...this.mcpCallHistory],
                costs: [...this.costHistory],
            };
        } catch (error) {
            const duration = Date.now() - startTime;
            return {
                success: false,
                error: this.formatError(error),
                duration,
                mcpCalls: [...this.mcpCallHistory],
                costs: [...this.costHistory],
            };
        } finally {
            // Clear history for next invocation
            this.mcpCallHistory = [];
            this.costHistory = [];
        }
    }

    /**
     * Execute a specific capability
     */
    async executeCapability(
        capability: string,
        parameters: Record<string, unknown>,
        context: AgentContext
    ): Promise<AgentResult> {
        const capabilityDef = this.config.capabilities.find((c) => c.name === capability);
        if (!capabilityDef) {
            return {
                success: false,
                error: {
                    code: 'CAPABILITY_NOT_FOUND',
                    message: `Capability '${capability}' not found in agent '${this.getName()}'`,
                },
                duration: 0,
            };
        }

        // Build prompt for this capability
        const prompt = this.buildCapabilityPrompt(capability, parameters, capabilityDef);

        return this.invoke(prompt, context);
    }

    /**
     * Get agent health status
     */
    async getHealth(): Promise<AgentHealthStatus> {
        try {
            // Check if Strands agent is responsive
            await this.strandsAgent.invoke('Health check');

            return {
                status: 'healthy',
                timestamp: new Date().toISOString(),
                details: {
                    mcpAdapters: Array.from(this.mcpAdapters.keys()),
                },
            };
        } catch (error) {
            return {
                status: 'unhealthy',
                timestamp: new Date().toISOString(),
                details: {
                    error: this.formatError(error),
                },
            };
        }
    }

    /**
     * Call an MCP adapter capability
     */
    protected async callMCP<T = unknown>(
        adapterName: string,
        capability: string,
        parameters: Record<string, unknown>,
        context: AgentContext
    ): Promise<MCPResponse<T>> {
        const adapter = this.mcpAdapters.get(adapterName);
        if (!adapter) {
            throw new Error(`MCP adapter '${adapterName}' not found`);
        }

        const request: MCPRequest = {
            id: `${context.executionId}-${Date.now()}`,
            timestamp: new Date().toISOString(),
            capability,
            parameters,
            actor: this.getName(),
        };

        const startTime = Date.now();
        const response = await adapter.execute<T>(request);
        const duration = Date.now() - startTime;

        // Record MCP call for provenance
        this.mcpCallHistory.push({
            adapter: adapterName,
            capability,
            request,
            response,
            duration,
        });

        return response;
    }

    /**
     * Build a contextual prompt with execution context
     */
    protected buildContextualPrompt(prompt: string, context: AgentContext): string {
        return `
Execution Context:
- Execution ID: ${context.executionId}
- Plan ID: ${context.planId}
- Step ID: ${context.stepId}
- Environment: ${context.environment}
${context.budgetPolicyId ? `- Budget Policy: ${context.budgetPolicyId}` : ''}

Task:
${prompt}

Please provide a structured response that can be parsed and used by the orchestrator.
`;
    }

    /**
     * Build a prompt for a specific capability
     */
    protected buildCapabilityPrompt(
        capability: string,
        parameters: Record<string, unknown>,
        capabilityDef: AgentCapability
    ): string {
        return `
Execute capability: ${capability}

Description: ${capabilityDef.description}

Parameters:
${JSON.stringify(parameters, null, 2)}

Please execute this capability and return the result in a structured format.
`;
    }

    /**
     * Format error into AgentError
     */
    protected formatError(error: unknown): AgentError {
        if (error instanceof Error) {
            return {
                code: 'AGENT_ERROR',
                message: error.message,
                details: { stack: error.stack },
                retryable: false,
            };
        }
        return {
            code: 'UNKNOWN_ERROR',
            message: String(error),
            retryable: false,
        };
    }

    /**
     * Track cost for an operation
     */
    protected trackCost(
        service: string,
        operation: string,
        cost: number,
        currency: string = 'GBP'
    ): void {
        this.costHistory.push({
            service,
            operation,
            cost,
            currency,
            timestamp: new Date().toISOString(),
        });
    }
}
