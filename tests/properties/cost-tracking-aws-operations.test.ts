/**
 * Property-Based Test: Cost Tracking for AWS Operations
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 20: Cost Tracking for AWS Operations
 * 
 * For any AWS operation executed through MCP adapters, the CostMonitorFinOpsAgent must create
 * a cost record containing service, operation, cost estimate, timestamp, and resource ID.
 * 
 * Validates: Requirements 20.2
 */

import fc from 'fast-check';

// Mock the Strands SDK to avoid ES module issues in Jest
jest.mock('@strands-agents/sdk', () => ({
    Agent: class MockAgent { },
    BedrockModel: class MockBedrockModel { },
}));

import { CostMonitorFinOpsAgent } from '../../Agents/CostMonitorFinOpsAgent';
import type { AgentContext } from '../../Agents/types';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 20: Cost Tracking for AWS Operations', () => {
        let agent: CostMonitorFinOpsAgent;
        const testContext: AgentContext = {
            executionId: 'test-execution',
            planId: 'test-plan',
            stepId: 'test-step',
            environment: 'dev',
            correlationId: 'test-correlation',
        };

        beforeEach(() => {
            agent = new CostMonitorFinOpsAgent();
            agent.clearCostRecords();
        });

        it('should create cost records for any AWS operation', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.constantFrom('GameLift', 'Cognito', 'DynamoDB', 'Lambda', 'S3', 'CloudWatch'),
                    fc.string({ minLength: 5, maxLength: 50 }), // operation
                    fc.integer({ min: 1, max: 10000 }).map(n => n / 100), // cost (convert pence to pounds)
                    fc.string({ minLength: 10, maxLength: 50 }), // budgetPolicyId
                    fc.option(fc.string({ minLength: 10, maxLength: 50 }), { nil: undefined }), // resourceId
                    fc.option(fc.dictionary(fc.string(), fc.string()), { nil: undefined }), // tags
                    async (service, operation, cost, budgetPolicyId, resourceId, tags) => {
                        const result = await agent.trackCostOperation(
                            service,
                            operation,
                            cost,
                            budgetPolicyId,
                            testContext,
                            {
                                currency: 'GBP',
                                resourceId,
                                tags: tags || {},
                            }
                        );

                        // Property: Operation should succeed
                        expect(result.success).toBe(true);
                        expect(result.result).toBeDefined();

                        // Property: Cost record should be created
                        const records = agent.getCostRecords(budgetPolicyId);
                        expect(records.length).toBeGreaterThan(0);

                        const record = records[records.length - 1]; // Get the last record

                        // Property: Record must have required fields
                        expect(record.recordId).toBeDefined();
                        expect(typeof record.recordId).toBe('string');
                        expect(record.recordId.length).toBeGreaterThan(0);

                        expect(record.timestamp).toBeDefined();
                        expect(typeof record.timestamp).toBe('string');
                        expect(new Date(record.timestamp).getTime()).not.toBeNaN();

                        expect(record.service).toBe(service);
                        expect(record.operation).toBe(operation);
                        expect(record.cost).toBe(cost);
                        expect(record.currency).toBe('GBP');
                        expect(record.budgetPolicyId).toBe(budgetPolicyId);

                        // Property: Optional fields should match if provided
                        if (resourceId) {
                            expect(record.resourceId).toBe(resourceId);
                        }

                        if (tags) {
                            expect(record.tags).toEqual(tags);
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should accumulate cost records for multiple operations', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 10, maxLength: 50 }), // budgetPolicyId
                    fc.array(
                        fc.record({
                            service: fc.constantFrom('GameLift', 'Cognito', 'DynamoDB', 'Lambda'),
                            operation: fc.string({ minLength: 5, maxLength: 30 }),
                            cost: fc.integer({ min: 1, max: 5000 }).map(n => n / 100),
                        }),
                        { minLength: 1, maxLength: 20 }
                    ),
                    async (budgetPolicyId, operations) => {
                        // Track all operations
                        for (const op of operations) {
                            await agent.trackCostOperation(
                                op.service,
                                op.operation,
                                op.cost,
                                budgetPolicyId,
                                testContext
                            );
                        }

                        // Property: All operations should be recorded
                        const records = agent.getCostRecords(budgetPolicyId);
                        expect(records.length).toBe(operations.length);

                        // Property: Total cost should match sum of individual costs
                        const totalCost = records.reduce((sum, record) => sum + record.cost, 0);
                        const expectedTotal = operations.reduce((sum, op) => sum + op.cost, 0);
                        expect(totalCost).toBeCloseTo(expectedTotal, 2);

                        // Property: Each record should have unique ID
                        const recordIds = new Set(records.map(r => r.recordId));
                        expect(recordIds.size).toBe(records.length);

                        // Property: Records should be in chronological order
                        for (let i = 1; i < records.length; i++) {
                            const prevTime = new Date(records[i - 1].timestamp).getTime();
                            const currTime = new Date(records[i].timestamp).getTime();
                            expect(currTime).toBeGreaterThanOrEqual(prevTime);
                        }
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should track costs separately for different budget policies', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.array(fc.string({ minLength: 10, maxLength: 50 }), { minLength: 2, maxLength: 5 }), // Multiple policy IDs
                    fc.array(fc.integer({ min: 1, max: 5000 }).map(n => n / 100), { minLength: 1, maxLength: 10 }), // Costs
                    async (policyIds, costs) => {
                        // Make policy IDs unique
                        const uniquePolicyIds = Array.from(new Set(policyIds));
                        if (uniquePolicyIds.length < 2) return; // Skip if not enough unique IDs

                        // Track costs for each policy
                        for (let i = 0; i < uniquePolicyIds.length; i++) {
                            const policyId = uniquePolicyIds[i];
                            const cost = costs[i % costs.length];

                            await agent.trackCostOperation(
                                'GameLift',
                                'CreateFleet',
                                cost,
                                policyId,
                                testContext
                            );
                        }

                        // Property: Each policy should have its own cost records
                        for (const policyId of uniquePolicyIds) {
                            const records = agent.getCostRecords(policyId);
                            expect(records.length).toBeGreaterThan(0);

                            // Property: All records should belong to the correct policy
                            for (const record of records) {
                                expect(record.budgetPolicyId).toBe(policyId);
                            }
                        }
                    }
                ),
                { numRuns: 30 }
            );
        });

        it('should handle edge case: zero cost operations', async () => {
            const budgetPolicyId = 'test-policy-zero';

            const result = await agent.trackCostOperation(
                'Lambda',
                'Invoke',
                0,
                budgetPolicyId,
                testContext
            );

            expect(result.success).toBe(true);

            const records = agent.getCostRecords(budgetPolicyId);
            expect(records.length).toBe(1);
            expect(records[0].cost).toBe(0);
        });

        it('should handle edge case: very small costs', async () => {
            const budgetPolicyId = 'test-policy-small';

            const result = await agent.trackCostOperation(
                'DynamoDB',
                'Query',
                0.0001,
                budgetPolicyId,
                testContext
            );

            expect(result.success).toBe(true);

            const records = agent.getCostRecords(budgetPolicyId);
            expect(records.length).toBe(1);
            expect(records[0].cost).toBe(0.0001);
        });

        it('should handle edge case: very large costs', async () => {
            const budgetPolicyId = 'test-policy-large';

            const result = await agent.trackCostOperation(
                'GameLift',
                'CreateFleet',
                999999.99,
                budgetPolicyId,
                testContext
            );

            expect(result.success).toBe(true);

            const records = agent.getCostRecords(budgetPolicyId);
            expect(records.length).toBe(1);
            expect(records[0].cost).toBe(999999.99);
        });

        it('should track costs by service for reporting', async () => {
            const budgetPolicyId = 'test-policy-services';

            // Track costs for different services
            await agent.trackCostOperation('GameLift', 'CreateFleet', 100, budgetPolicyId, testContext);
            await agent.trackCostOperation('GameLift', 'UpdateFleet', 50, budgetPolicyId, testContext);
            await agent.trackCostOperation('Cognito', 'CreateUserPool', 20, budgetPolicyId, testContext);
            await agent.trackCostOperation('DynamoDB', 'CreateTable', 30, budgetPolicyId, testContext);

            const records = agent.getCostRecords(budgetPolicyId);

            // Property: Should be able to group by service
            const byService: Record<string, number> = {};
            for (const record of records) {
                byService[record.service] = (byService[record.service] || 0) + record.cost;
            }

            expect(byService['GameLift']).toBe(150);
            expect(byService['Cognito']).toBe(20);
            expect(byService['DynamoDB']).toBe(30);
        });

        it('should include timestamps for all cost records', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 10, maxLength: 50 }),
                    fc.array(fc.integer({ min: 1, max: 10000 }).map(n => n / 100), { minLength: 1, maxLength: 10 }),
                    async (budgetPolicyId, costs) => {
                        const startTime = Date.now();

                        for (const cost of costs) {
                            await agent.trackCostOperation(
                                'GameLift',
                                'CreateFleet',
                                cost,
                                budgetPolicyId,
                                testContext
                            );
                        }

                        const endTime = Date.now();
                        const records = agent.getCostRecords(budgetPolicyId);

                        // Property: All timestamps should be within the test execution window
                        for (const record of records) {
                            const recordTime = new Date(record.timestamp).getTime();
                            expect(recordTime).toBeGreaterThanOrEqual(startTime);
                            expect(recordTime).toBeLessThanOrEqual(endTime);
                        }
                    }
                ),
                { numRuns: 30 }
            );
        });
    });
});
