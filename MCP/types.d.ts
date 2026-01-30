/**
 * Core types for MCP (Model Context Protocol) adapters
 *
 * All MCP adapters follow a capability-based interface pattern where:
 * 1. Agents request capabilities (e.g., "build_unreal_project") rather than direct API calls
 * 2. Every adapter has a mock implementation for local development
 * 3. All operations are logged with timestamps and actor information for provenance
 * 4. Consistent error reporting across all external systems
 */
export interface MCPRequest {
    id: string;
    timestamp: string;
    capability: string;
    parameters: Record<string, unknown>;
    timeout?: number;
    actor?: string;
}
export interface MCPResponse<T = unknown> {
    id: string;
    requestId: string;
    timestamp: string;
    success: boolean;
    result?: T;
    error?: MCPError;
    provenance?: ProvenanceRecord;
}
export interface MCPError {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    retryable?: boolean;
}
export interface ProvenanceRecord {
    timestamp: string;
    actor: string;
    operation: string;
    parameters: Record<string, unknown>;
    result?: unknown;
    duration?: number;
}
export interface MCPAdapterConfig {
    mockMode: boolean;
    timeout?: number;
    retryAttempts?: number;
    logProvenance?: boolean;
}
export interface MCPCapability {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
    mockable: boolean;
}
/**
 * Base interface that all MCP adapters must implement
 */
export interface IMCPAdapter {
    /**
     * Get the adapter name
     */
    getName(): string;
    /**
     * Get list of supported capabilities
     */
    getCapabilities(): MCPCapability[];
    /**
     * Check if adapter is in mock mode
     */
    isMockMode(): boolean;
    /**
     * Execute a capability request
     */
    execute<T = unknown>(request: MCPRequest): Promise<MCPResponse<T>>;
    /**
     * Get provenance records for audit trail
     */
    getProvenanceRecords(): ProvenanceRecord[];
    /**
     * Clear provenance records (for testing)
     */
    clearProvenanceRecords(): void;
}
/**
 * Configuration for rate limiting
 */
export interface RateLimitConfig {
    maxRequestsPerMinute: number;
    maxRequestsPerHour: number;
    maxConcurrentRequests: number;
}
/**
 * Rate limiter state
 */
export interface RateLimiterState {
    requestsThisMinute: number;
    requestsThisHour: number;
    currentConcurrentRequests: number;
    lastMinuteReset: number;
    lastHourReset: number;
}
//# sourceMappingURL=types.d.ts.map