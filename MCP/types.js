/**
 * Core types for MCP (Model Context Protocol) adapters
 *
 * All MCP adapters follow a capability-based interface pattern where:
 * 1. Agents request capabilities (e.g., "build_unreal_project") rather than direct API calls
 * 2. Every adapter has a mock implementation for local development
 * 3. All operations are logged with timestamps and actor information for provenance
 * 4. Consistent error reporting across all external systems
 */
export {};
//# sourceMappingURL=types.js.map