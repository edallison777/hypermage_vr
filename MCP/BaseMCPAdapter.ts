/**
 * Base MCP Adapter implementation
 * 
 * Provides common functionality for all MCP adapters:
 * - Mock mode switching
 * - Provenance logging
 * - Error handling
 * - Rate limiting
 */

import {
    IMCPAdapter,
    MCPRequest,
    MCPResponse,
    MCPCapability,
    MCPAdapterConfig,
    ProvenanceRecord,
    RateLimitConfig,
    RateLimiterState,
    MCPError,
} from './types';

export abstract class BaseMCPAdapter implements IMCPAdapter {
    protected config: MCPAdapterConfig;
    protected provenanceRecords: ProvenanceRecord[] = [];
    protected rateLimitConfig?: RateLimitConfig;
    protected rateLimiterState?: RateLimiterState;

    constructor(config: MCPAdapterConfig, rateLimitConfig?: RateLimitConfig) {
        this.config = {
            mockMode: config.mockMode ?? false,
            timeout: config.timeout ?? 30000,
            retryAttempts: config.retryAttempts ?? 3,
            logProvenance: config.logProvenance ?? true,
        };

        if (rateLimitConfig) {
            this.rateLimitConfig = rateLimitConfig;
            this.rateLimiterState = {
                requestsThisMinute: 0,
                requestsThisHour: 0,
                currentConcurrentRequests: 0,
                lastMinuteReset: Date.now(),
                lastHourReset: Date.now(),
            };
        }
    }

    abstract getName(): string;
    abstract getCapabilities(): MCPCapability[];
    protected abstract executeCapability<T>(request: MCPRequest): Promise<T>;
    protected abstract executeMockCapability<T>(request: MCPRequest): Promise<T>;

    isMockMode(): boolean {
        return this.config.mockMode;
    }

    async execute<T = unknown>(request: MCPRequest): Promise<MCPResponse<T>> {
        const startTime = Date.now();

        // Check rate limits
        if (this.rateLimitConfig && this.rateLimiterState) {
            const rateLimitError = this.checkRateLimit();
            if (rateLimitError) {
                return this.createErrorResponse<T>(request.id, rateLimitError, startTime);
            }
        }

        try {
            // Increment concurrent requests
            if (this.rateLimiterState) {
                this.rateLimiterState.currentConcurrentRequests++;
            }

            // Execute capability (mock or real)
            const result = this.config.mockMode
                ? await this.executeMockCapability<T>(request)
                : await this.executeCapability<T>(request);

            const duration = Date.now() - startTime;

            // Log provenance
            if (this.config.logProvenance) {
                this.logProvenance({
                    timestamp: new Date().toISOString(),
                    actor: request.actor || 'unknown',
                    operation: `${this.getName()}.${request.capability}`,
                    parameters: request.parameters,
                    result,
                    duration,
                });
            }

            return {
                id: this.generateId(),
                requestId: request.id,
                timestamp: new Date().toISOString(),
                success: true,
                result,
                provenance: this.config.logProvenance
                    ? {
                        timestamp: new Date().toISOString(),
                        actor: request.actor || 'unknown',
                        operation: `${this.getName()}.${request.capability}`,
                        parameters: request.parameters,
                        result,
                        duration,
                    }
                    : undefined,
            };
        } catch (error) {
            const mcpError: MCPError = {
                code: error instanceof Error ? error.name : 'UNKNOWN_ERROR',
                message: error instanceof Error ? error.message : 'An unknown error occurred',
                details: error instanceof Error ? { stack: error.stack } : {},
                retryable: this.isRetryableError(error),
            };

            return this.createErrorResponse<T>(request.id, mcpError, startTime);
        } finally {
            // Decrement concurrent requests
            if (this.rateLimiterState) {
                this.rateLimiterState.currentConcurrentRequests--;
            }
        }
    }

    getProvenanceRecords(): ProvenanceRecord[] {
        return [...this.provenanceRecords];
    }

    clearProvenanceRecords(): void {
        this.provenanceRecords = [];
    }

    protected logProvenance(record: ProvenanceRecord): void {
        this.provenanceRecords.push(record);
    }

    protected generateId(): string {
        return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }

    protected createErrorResponse<T>(
        requestId: string,
        error: MCPError,
        startTime: number
    ): MCPResponse<T> {
        const duration = Date.now() - startTime;

        return {
            id: this.generateId(),
            requestId,
            timestamp: new Date().toISOString(),
            success: false,
            error,
            provenance: this.config.logProvenance
                ? {
                    timestamp: new Date().toISOString(),
                    actor: 'system',
                    operation: `${this.getName()}.error`,
                    parameters: {},
                    result: error,
                    duration,
                }
                : undefined,
        };
    }

    protected isRetryableError(error: unknown): boolean {
        if (error instanceof Error) {
            const retryableErrors = ['ETIMEDOUT', 'ECONNRESET', 'ENOTFOUND', 'RATE_LIMIT_EXCEEDED'];
            return retryableErrors.some((code) => error.message.includes(code));
        }
        return false;
    }

    protected checkRateLimit(): MCPError | null {
        if (!this.rateLimitConfig || !this.rateLimiterState) {
            return null;
        }

        const now = Date.now();

        // Reset minute counter if needed
        if (now - this.rateLimiterState.lastMinuteReset > 60000) {
            this.rateLimiterState.requestsThisMinute = 0;
            this.rateLimiterState.lastMinuteReset = now;
        }

        // Reset hour counter if needed
        if (now - this.rateLimiterState.lastHourReset > 3600000) {
            this.rateLimiterState.requestsThisHour = 0;
            this.rateLimiterState.lastHourReset = now;
        }

        // Check limits
        if (
            this.rateLimiterState.requestsThisMinute >= this.rateLimitConfig.maxRequestsPerMinute
        ) {
            return {
                code: 'RATE_LIMIT_EXCEEDED',
                message: 'Rate limit exceeded: too many requests per minute',
                retryable: true,
            };
        }

        if (this.rateLimiterState.requestsThisHour >= this.rateLimitConfig.maxRequestsPerHour) {
            return {
                code: 'RATE_LIMIT_EXCEEDED',
                message: 'Rate limit exceeded: too many requests per hour',
                retryable: true,
            };
        }

        if (
            this.rateLimiterState.currentConcurrentRequests >=
            this.rateLimitConfig.maxConcurrentRequests
        ) {
            return {
                code: 'RATE_LIMIT_EXCEEDED',
                message: 'Rate limit exceeded: too many concurrent requests',
                retryable: true,
            };
        }

        // Increment counters
        this.rateLimiterState.requestsThisMinute++;
        this.rateLimiterState.requestsThisHour++;

        return null;
    }

    protected async delay(ms: number): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
}
