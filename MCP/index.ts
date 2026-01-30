/**
 * MCP Adapters - Model Context Protocol adapters for external systems
 * 
 * All adapters follow a capability-based interface pattern with mock support
 */

export * from './types';
export * from './BaseMCPAdapter';
export * from './adapters/UnrealMCPAdapter';
export * from './adapters/AWSMCPAdapter';
export * from './adapters/GitHubMCPAdapter';
