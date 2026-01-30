/**
 * Core types for the Agent framework using Strands SDK
 * 
 * All agents are built using Strands Agent SDK and deployed to AWS AgentCore runtime.
 * Agents communicate through structured JSON messages and coordinate via the Orchestrator.
 */

import type { MCPRequest, MCPResponse } from '../MCP/types.js';

/**
 * Agent message types for inter-agent communication
 */
export interface AgentMessage {
    id: string;
    timestamp: string;
    from: string;
    to: string;
    type: 'request' | 'response' | 'event' | 'error';
    payload: unknown;
    correlationId?: string;
}

export interface AgentRequest extends AgentMessage {
    type: 'request';
    payload: {
        capability: string;
        parameters: Record<string, unknown>;
        timeout?: number;
    };
}

export interface AgentResponse extends AgentMessage {
    type: 'response';
    payload: {
        success: boolean;
        result?: unknown;
        error?: AgentError;
    };
}

export interface AgentEvent extends AgentMessage {
    type: 'event';
    payload: {
        eventType: string;
        data: Record<string, unknown>;
    };
}

export interface AgentError {
    code: string;
    message: string;
    details?: unknown;
    retryable?: boolean;
}

/**
 * Agent configuration
 */
export interface AgentConfig {
    name: string;
    description: string;
    capabilities: AgentCapability[];
    model?: ModelConfig;
    tools?: unknown[]; // Strands tools
    maxRetries?: number;
    timeout?: number;
}

export interface AgentCapability {
    name: string;
    description: string;
    parameters: Record<string, unknown>; // JSON Schema
    mcpAdapters?: string[]; // MCP adapters this capability uses
}

export interface ModelConfig {
    provider: 'bedrock' | 'anthropic' | 'openai' | 'gemini';
    modelId: string;
    region?: string;
    temperature?: number;
    maxTokens?: number;
}

/**
 * Agent execution context
 */
export interface AgentContext {
    executionId: string;
    planId: string;
    stepId: string;
    environment: 'dev' | 'prod';
    budgetPolicyId?: string;
    correlationId?: string;
}

/**
 * Agent result from invocation
 */
export interface AgentResult {
    success: boolean;
    result?: unknown;
    error?: AgentError;
    artifacts?: AgentArtifact[];
    costs?: AgentCostRecord[];
    duration: number; // milliseconds
    mcpCalls?: MCPCallRecord[];
}

export interface AgentArtifact {
    id: string;
    type: string;
    name: string;
    path: string;
    metadata?: Record<string, unknown>;
}

export interface AgentCostRecord {
    service: string;
    operation: string;
    cost: number;
    currency: string;
    timestamp: string;
}

export interface MCPCallRecord {
    adapter: string;
    capability: string;
    request: MCPRequest;
    response: MCPResponse;
    duration: number;
}

/**
 * Base interface that all agents must implement
 */
export interface IAgent {
    /**
     * Get agent name
     */
    getName(): string;

    /**
     * Get agent description
     */
    getDescription(): string;

    /**
     * Get list of capabilities this agent provides
     */
    getCapabilities(): AgentCapability[];

    /**
     * Invoke the agent with a natural language prompt
     */
    invoke(prompt: string, context: AgentContext): Promise<AgentResult>;

    /**
     * Execute a specific capability
     */
    executeCapability(
        capability: string,
        parameters: Record<string, unknown>,
        context: AgentContext
    ): Promise<AgentResult>;

    /**
     * Get agent health status
     */
    getHealth(): Promise<AgentHealthStatus>;
}

export interface AgentHealthStatus {
    status: 'healthy' | 'degraded' | 'unhealthy';
    timestamp: string;
    details?: Record<string, unknown>;
}
