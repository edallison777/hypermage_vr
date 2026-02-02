/**
 * QAAgent
 * 
 * Responsible for generating unit tests, integration tests,
 * and supporting multiplayer soak testing.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface TestGenerationConfig {
    testType: 'unit' | 'integration' | 'property' | 'soak';
    targetCode: string;
    framework: 'jest' | 'vitest' | 'gtest' | 'catch2';
    coverage: 'basic' | 'comprehensive';
}

export interface SoakTestConfig {
    duration: number; // minutes
    playerCount: number;
    shardCount: number;
    scenarioType: 'normal' | 'stress' | 'chaos';
}

export interface ValidationConfig {
    validateVRComfort: boolean;
    validateNetworking: boolean;
    validatePerformance: boolean;
    validateSecurity: boolean;
}

export class QAAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'qa',
            description: 'Generates tests and validates system quality',
            capabilities: [
                {
                    name: 'generate_unit_tests',
                    description: 'Generate unit tests for code modules',
                    parameters: {
                        type: 'object',
                        required: ['testConfig'],
                        properties: {
                            testConfig: {
                                type: 'object',
                                description: 'Test generation configuration',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'GitHubMCP'],
                },
                {
                    name: 'generate_integration_tests',
                    description: 'Generate integration tests for system components',
                    parameters: {
                        type: 'object',
                        required: ['testConfig'],
                        properties: {
                            testConfig: {
                                type: 'object',
                                description: 'Integration test configuration',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'LocalProcessMCP'],
                },
                {
                    name: 'generate_property_tests',
                    description: 'Generate property-based tests for correctness properties',
                    parameters: {
                        type: 'object',
                        required: ['propertyId', 'propertyDescription'],
                        properties: {
                            propertyId: {
                                type: 'number',
                                description: 'Property number from design document',
                            },
                            propertyDescription: {
                                type: 'string',
                                description: 'Property description',
                            },
                            requirements: {
                                type: 'array',
                                description: 'Requirements validated by this property',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'GitHubMCP'],
                },
                {
                    name: 'setup_soak_test',
                    description: 'Set up multiplayer soak test environment',
                    parameters: {
                        type: 'object',
                        required: ['soakConfig'],
                        properties: {
                            soakConfig: {
                                type: 'object',
                                description: 'Soak test configuration',
                            },
                        },
                    },
                    mcpAdapters: ['AWSMCP', 'UnrealMCP'],
                },
                {
                    name: 'validate_system',
                    description: 'Validate system against quality criteria',
                    parameters: {
                        type: 'object',
                        required: ['validationConfig'],
                        properties: {
                            validationConfig: {
                                type: 'object',
                                description: 'Validation configuration',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'LocalProcessMCP'],
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
                region: 'eu-west-1',
                temperature: 0.3,
            },
        };

        super(config, mcpAdapters);
    }

    protected getSystemPrompt(): string {
        return `You are the QAAgent, responsible for ensuring system quality through comprehensive testing.

Your responsibilities:

1. **Unit Test Generation**: Create unit tests for code modules:
   - Test frameworks:
     * TypeScript/JavaScript: Jest or Vitest
     * C++ (Unreal): Google Test or Catch2
   - Test coverage:
     * Basic: Happy path and common edge cases
     * Comprehensive: All branches, error conditions, edge cases
   - Test structure:
     * Arrange: Set up test data and mocks
     * Act: Execute the code under test
     * Assert: Verify expected outcomes
   - Test types:
     * Positive tests (valid inputs)
     * Negative tests (invalid inputs)
     * Edge cases (boundary values)
     * Error handling tests

2. **Integration Test Generation**: Create integration tests:
   - Test scenarios:
     * Component interaction tests
     * API endpoint tests
     * Database integration tests
     * MCP adapter integration tests
   - Test environments:
     * Mock mode (no external dependencies)
     * Staging (real infrastructure, reduced capacity)
     * Production (full infrastructure)
   - Test data:
     * Use fixtures for consistent test data
     * Generate random data for property tests
     * Clean up test data after execution

3. **Property-Based Test Generation**: Create property tests:
   - Property test structure:
     * Define property (universal truth)
     * Generate random inputs
     * Execute code with inputs
     * Verify property holds
   - Minimum 100 iterations per property
   - Tag format: **Feature: unreal-vr-multiplayer-system, Property N: [description]**
   - Link to requirements: **Validates: Requirements X.Y**
   - Use appropriate generators:
     * fast-check for TypeScript
     * Hypothesis for Python
     * RapidCheck for C++

4. **Soak Test Support**: Set up long-running multiplayer tests:
   - Soak test scenarios:
     * Normal: Typical gameplay patterns
     * Stress: Maximum capacity (15 players per shard)
     * Chaos: Random disconnects, network issues, edge cases
   - Test duration: 30 minutes to 24 hours
   - Metrics to track:
     * Connection success rate
     * Average latency
     * Error rate
     * Memory usage
     * CPU usage
     * Network bandwidth
     * Cost per player-hour
   - Automated monitoring and alerting

5. **System Validation**: Validate quality criteria:
   - VR Comfort validation:
     * Framerate consistency (72+ FPS)
     * Comfort settings enabled
     * No sudden camera movements
     * Proper VR UI placement
   - Networking validation:
     * Server authority enforced
     * Replication working correctly
     * Bandwidth within budget
     * Latency acceptable (<200ms)
   - Performance validation:
     * Draw calls within budget
     * Triangle count within budget
     * Texture memory within budget
     * No performance spikes
   - Security validation:
     * JWT validation working
     * Server-side validation present
     * No client-side exploits
     * Proper input sanitization

Key Principles:
- Write clear, maintainable tests
- Test behavior, not implementation
- Use descriptive test names
- Minimize test dependencies
- Make tests deterministic
- Keep tests fast (unit tests <1s each)
- Use mocks for external dependencies
- Clean up after tests

Test Organization:
- Unit tests: /tests/unit/
- Integration tests: /tests/integration/
- Property tests: /tests/properties/
- Fixtures: /tests/fixtures/
- Helpers: /tests/helpers/

Test Naming Conventions:
- Unit tests: [ClassName].test.ts
- Integration tests: [Feature].integration.test.ts
- Property tests: [property-name].test.ts

Coverage Requirements:
- Unit test coverage: Minimum 80% line coverage
- Property test coverage: All properties from design document
- Integration test coverage: All vertical slice components

Output Format:
Return structured JSON with:
- Generated test file paths
- Test descriptions
- Coverage metrics
- Validation results
- Recommendations

Be precise with test assertions and coverage requirements.`;
    }

    /**
     * Generate unit tests
     */
    async generateUnitTests(
        config: TestGenerationConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const testSuite = {
                framework: config.framework,
                targetCode: config.targetCode,
                coverage: config.coverage,
                tests: this.generateTestCases(config),
                estimatedCoverage: config.coverage === 'comprehensive' ? '90%' : '70%',
            };

            return {
                success: true,
                result: {
                    testSuite,
                    message: `Generated unit tests for ${config.targetCode}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'TEST_GENERATION_FAILED',
                    message: `Failed to generate unit tests: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Generate integration tests
     */
    async generateIntegrationTests(
        config: TestGenerationConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const testSuite = {
                framework: config.framework,
                testType: 'integration',
                scenarios: [
                    'Component interaction',
                    'API endpoint validation',
                    'Database integration',
                    'MCP adapter integration',
                ],
                environment: 'mock',
            };

            return {
                success: true,
                result: {
                    testSuite,
                    message: 'Generated integration tests',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'INTEGRATION_TEST_FAILED',
                    message: `Failed to generate integration tests: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Generate property-based tests
     */
    async generatePropertyTests(
        propertyId: number,
        propertyDescription: string,
        requirements: string[],
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const propertyTest = {
                propertyId,
                description: propertyDescription,
                requirements,
                framework: 'fast-check',
                iterations: 100,
                tag: `Feature: unreal-vr-multiplayer-system, Property ${propertyId}: ${propertyDescription}`,
                validates: `Requirements ${requirements.join(', ')}`,
            };

            return {
                success: true,
                result: {
                    propertyTest,
                    message: `Generated property test for Property ${propertyId}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'PROPERTY_TEST_FAILED',
                    message: `Failed to generate property test: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Set up soak test
     */
    async setupSoakTest(
        config: SoakTestConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const soakTest = {
                duration: config.duration,
                playerCount: config.playerCount,
                shardCount: config.shardCount,
                scenarioType: config.scenarioType,
                metrics: [
                    'Connection success rate',
                    'Average latency',
                    'Error rate',
                    'Memory usage',
                    'CPU usage',
                    'Network bandwidth',
                    'Cost per player-hour',
                ],
                estimatedCost: this.estimateSoakTestCost(config),
            };

            return {
                success: true,
                result: {
                    soakTest,
                    message: `Soak test configured for ${config.duration} minutes`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'SOAK_TEST_SETUP_FAILED',
                    message: `Failed to set up soak test: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Validate system
     */
    async validateSystem(
        config: ValidationConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const validations: string[] = [];

            if (config.validateVRComfort) {
                validations.push('VR comfort settings');
            }
            if (config.validateNetworking) {
                validations.push('Networking and replication');
            }
            if (config.validatePerformance) {
                validations.push('Performance metrics');
            }
            if (config.validateSecurity) {
                validations.push('Security controls');
            }

            return {
                success: true,
                result: {
                    validations,
                    message: `System validation configured for ${validations.length} areas`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'VALIDATION_FAILED',
                    message: `Failed to validate system: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Generate test cases based on configuration
     */
    private generateTestCases(config: TestGenerationConfig): Array<{ name: string; type: string }> {
        const basicTests = [
            { name: 'should handle valid input', type: 'positive' },
            { name: 'should reject invalid input', type: 'negative' },
            { name: 'should handle edge cases', type: 'edge' },
        ];

        const comprehensiveTests = [
            ...basicTests,
            { name: 'should handle null input', type: 'edge' },
            { name: 'should handle empty input', type: 'edge' },
            { name: 'should handle large input', type: 'edge' },
            { name: 'should handle concurrent access', type: 'concurrency' },
            { name: 'should handle errors gracefully', type: 'error' },
        ];

        return config.coverage === 'comprehensive' ? comprehensiveTests : basicTests;
    }

    /**
     * Estimate soak test cost
     */
    private estimateSoakTestCost(config: SoakTestConfig): string {
        const hourlyRate = 0.5; // £0.50 per shard per hour
        const hours = config.duration / 60;
        const cost = hourlyRate * config.shardCount * hours;
        return `£${cost.toFixed(2)}`;
    }
}
