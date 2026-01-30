/**
 * Agent Communication Protocol
 * 
 * Handles message routing, correlation IDs, timeout handling, and retry logic
 * for inter-agent communication coordinated by the Orchestrator.
 */

import type {
    AgentMessage,
    AgentRequest,
    AgentResponse,
    AgentEvent,
    AgentError,
} from './types.js';

/**
 * Configuration for agent communication
 */
export interface CommunicationConfig {
    defaultTimeout: number; // milliseconds
    maxRetries: number;
    retryDelayMs: number;
    exponentialBackoff: boolean;
}

/**
 * Message router for agent-to-agent communication
 */
export class AgentMessageRouter {
    private pendingRequests: Map<string, PendingRequest>;
    private messageHandlers: Map<string, MessageHandler>;
    private config: CommunicationConfig;

    constructor(config?: Partial<CommunicationConfig>) {
        this.pendingRequests = new Map();
        this.messageHandlers = new Map();
        this.config = {
            defaultTimeout: 30000, // 30 seconds
            maxRetries: 3,
            retryDelayMs: 1000,
            exponentialBackoff: true,
            ...config,
        };
    }

    /**
     * Register a message handler for an agent
     */
    registerHandler(agentName: string, handler: MessageHandler): void {
        this.messageHandlers.set(agentName, handler);
    }

    /**
     * Unregister a message handler
     */
    unregisterHandler(agentName: string): void {
        this.messageHandlers.delete(agentName);
    }

    /**
     * Send a request to another agent
     */
    async sendRequest(
        from: string,
        to: string,
        capability: string,
        parameters: Record<string, unknown>,
        options?: RequestOptions
    ): Promise<AgentResponse> {
        const request = this.createRequest(from, to, capability, parameters, options);

        return this.sendWithRetry(request, options?.retries ?? this.config.maxRetries);
    }

    /**
     * Send a request with retry logic
     */
    private async sendWithRetry(
        request: AgentRequest,
        retriesLeft: number
    ): Promise<AgentResponse> {
        try {
            return await this.sendRequestInternal(request);
        } catch (error) {
            if (retriesLeft > 0 && this.isRetryable(error)) {
                const delay = this.calculateRetryDelay(
                    this.config.maxRetries - retriesLeft
                );
                await this.sleep(delay);
                return this.sendWithRetry(request, retriesLeft - 1);
            }
            throw error;
        }
    }

    /**
     * Internal request sending logic
     */
    private async sendRequestInternal(request: AgentRequest): Promise<AgentResponse> {
        const handler = this.messageHandlers.get(request.to);
        if (!handler) {
            throw new Error(`No handler registered for agent: ${request.to}`);
        }

        const timeout = request.payload.timeout ?? this.config.defaultTimeout;

        // Create pending request tracker
        const pending = this.createPendingRequest(request, timeout);
        this.pendingRequests.set(request.id, pending);

        try {
            // Send request to handler
            const response = await Promise.race([
                handler(request),
                this.createTimeoutPromise(timeout, request.id),
            ]);

            // Clean up pending request
            this.pendingRequests.delete(request.id);

            return response;
        } catch (error) {
            // Clean up pending request
            this.pendingRequests.delete(request.id);
            throw error;
        }
    }

    /**
     * Send an event (fire and forget)
     */
    async sendEvent(
        from: string,
        to: string,
        eventType: string,
        data: Record<string, unknown>
    ): Promise<void> {
        const event: AgentEvent = {
            id: this.generateMessageId(),
            timestamp: new Date().toISOString(),
            from,
            to,
            type: 'event',
            payload: {
                eventType,
                data,
            },
        };

        const handler = this.messageHandlers.get(to);
        if (handler) {
            // Fire and forget - don't wait for response
            handler(event).catch((error) => {
                console.error(`Error handling event from ${from} to ${to}:`, error);
            });
        }
    }

    /**
     * Create a request message
     */
    private createRequest(
        from: string,
        to: string,
        capability: string,
        parameters: Record<string, unknown>,
        options?: RequestOptions
    ): AgentRequest {
        return {
            id: this.generateMessageId(),
            timestamp: new Date().toISOString(),
            from,
            to,
            type: 'request',
            payload: {
                capability,
                parameters,
                timeout: options?.timeout,
            },
            correlationId: options?.correlationId,
        };
    }

    /**
     * Create a pending request tracker
     */
    private createPendingRequest(
        request: AgentRequest,
        timeout: number
    ): PendingRequest {
        return {
            request,
            startTime: Date.now(),
            timeout,
        };
    }

    /**
     * Create a timeout promise
     */
    private createTimeoutPromise(
        timeout: number,
        requestId: string
    ): Promise<AgentResponse> {
        return new Promise((_, reject) => {
            setTimeout(() => {
                reject(
                    new AgentTimeoutError(
                        `Request ${requestId} timed out after ${timeout}ms`
                    )
                );
            }, timeout);
        });
    }

    /**
     * Calculate retry delay with optional exponential backoff
     */
    private calculateRetryDelay(attemptNumber: number): number {
        if (this.config.exponentialBackoff) {
            return this.config.retryDelayMs * Math.pow(2, attemptNumber);
        }
        return this.config.retryDelayMs;
    }

    /**
     * Check if an error is retryable
     */
    private isRetryable(error: unknown): boolean {
        if (error instanceof AgentTimeoutError) {
            return true;
        }
        if (error instanceof Error) {
            // Check if error message indicates a transient issue
            const message = error.message.toLowerCase();
            return (
                message.includes('timeout') ||
                message.includes('network') ||
                message.includes('connection') ||
                message.includes('unavailable')
            );
        }
        return false;
    }

    /**
     * Generate a unique message ID
     */
    private generateMessageId(): string {
        return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Sleep utility
     */
    private sleep(ms: number): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    /**
     * Get pending requests (for monitoring)
     */
    getPendingRequests(): PendingRequestInfo[] {
        const now = Date.now();
        return Array.from(this.pendingRequests.values()).map((pending) => ({
            requestId: pending.request.id,
            from: pending.request.from,
            to: pending.request.to,
            capability: pending.request.payload.capability,
            elapsedMs: now - pending.startTime,
            timeoutMs: pending.timeout,
        }));
    }

    /**
     * Clear all pending requests (for cleanup)
     */
    clearPendingRequests(): void {
        this.pendingRequests.clear();
    }
}

/**
 * Message handler function type
 */
export type MessageHandler = (message: AgentMessage) => Promise<AgentResponse>;

/**
 * Request options
 */
export interface RequestOptions {
    timeout?: number;
    retries?: number;
    correlationId?: string;
}

/**
 * Pending request tracker
 */
interface PendingRequest {
    request: AgentRequest;
    startTime: number;
    timeout: number;
}

/**
 * Pending request info for monitoring
 */
export interface PendingRequestInfo {
    requestId: string;
    from: string;
    to: string;
    capability: string;
    elapsedMs: number;
    timeoutMs: number;
}

/**
 * Agent timeout error
 */
export class AgentTimeoutError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AgentTimeoutError';
    }
}

/**
 * Correlation ID manager for tracking related messages
 */
export class CorrelationIdManager {
    private correlations: Map<string, CorrelationContext>;

    constructor() {
        this.correlations = new Map();
    }

    /**
     * Create a new correlation ID
     */
    create(context: Partial<CorrelationContext>): string {
        const correlationId = `corr-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        this.correlations.set(correlationId, {
            correlationId,
            createdAt: new Date().toISOString(),
            messages: [],
            ...context,
        });
        return correlationId;
    }

    /**
     * Add a message to a correlation
     */
    addMessage(correlationId: string, message: AgentMessage): void {
        const context = this.correlations.get(correlationId);
        if (context) {
            context.messages.push({
                messageId: message.id,
                timestamp: message.timestamp,
                from: message.from,
                to: message.to,
                type: message.type,
            });
        }
    }

    /**
     * Get correlation context
     */
    getContext(correlationId: string): CorrelationContext | undefined {
        return this.correlations.get(correlationId);
    }

    /**
     * Get all messages in a correlation
     */
    getMessages(correlationId: string): MessageInfo[] {
        const context = this.correlations.get(correlationId);
        return context?.messages ?? [];
    }

    /**
     * Clear a correlation
     */
    clear(correlationId: string): void {
        this.correlations.delete(correlationId);
    }

    /**
     * Clear old correlations (older than maxAgeMs)
     */
    clearOld(maxAgeMs: number): number {
        const now = Date.now();
        let cleared = 0;

        for (const [correlationId, context] of this.correlations.entries()) {
            const age = now - new Date(context.createdAt).getTime();
            if (age > maxAgeMs) {
                this.correlations.delete(correlationId);
                cleared++;
            }
        }

        return cleared;
    }
}

/**
 * Correlation context
 */
export interface CorrelationContext {
    correlationId: string;
    createdAt: string;
    executionId?: string;
    planId?: string;
    stepId?: string;
    messages: MessageInfo[];
}

/**
 * Message info for correlation tracking
 */
export interface MessageInfo {
    messageId: string;
    timestamp: string;
    from: string;
    to: string;
    type: string;
}

/**
 * Response builder utility
 */
export class ResponseBuilder {
    /**
     * Create a success response
     */
    static success(
        request: AgentRequest,
        result: unknown
    ): AgentResponse {
        return {
            id: this.generateMessageId(),
            timestamp: new Date().toISOString(),
            from: request.to,
            to: request.from,
            type: 'response',
            payload: {
                success: true,
                result,
            },
            correlationId: request.correlationId,
        };
    }

    /**
     * Create an error response
     */
    static error(
        request: AgentRequest,
        error: AgentError
    ): AgentResponse {
        return {
            id: this.generateMessageId(),
            timestamp: new Date().toISOString(),
            from: request.to,
            to: request.from,
            type: 'response',
            payload: {
                success: false,
                error,
            },
            correlationId: request.correlationId,
        };
    }

    /**
     * Create an error from exception
     */
    static errorFromException(
        request: AgentRequest,
        exception: unknown
    ): AgentResponse {
        const error: AgentError = {
            code: 'AGENT_ERROR',
            message: exception instanceof Error ? exception.message : String(exception),
            details: exception instanceof Error ? { stack: exception.stack } : undefined,
            retryable: false,
        };

        return this.error(request, error);
    }

    private static generateMessageId(): string {
        return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
}
