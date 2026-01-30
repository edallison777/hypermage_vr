/**
 * Property-Based Test: Cost Limit Enforcement
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 12: Cost Limit Enforcement
 * 
 * For any AWS operation that would cause total costs to exceed the budget policy limit,
 * the CostMonitorFinOpsAgent must block the operation and return a budget exceeded error.
 * 
 * Validates: Requirements 7.7, 20.4
 */

import fc from 'fast-check';

// Mock the Strands SDK to avoid ES module issues in Jest
jest.mock('@strands-agents/sdk', () => ({
    Agent: class MockAgent { },
    BedrockModel: class MockBedrockModel { },
}));

import { CostMonitorFinOpsAgent } from '../../Agents/CostMonitorFinOpsAgent';
import type { BudgetPolicy } from '../../Agents/CostMonitorFinOpsAgent';
import type { AgentContext } from '../../Agents/types';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 12: Cost Limit Enforcement', () => {
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

        it('should block operations that would exceed total budget limit', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 100, max: 1000 }), // Budget limit
                    fc.array(fc.integer({ min: 1, max: 100 }), { minLength: 1, maxLength: 10 }), // Existing costs
                    fc.integer({ min: 1, max: 500 }), // New operation cost
                    async (budgetLimit, existingCosts, newOperationCost) => {
                        // Create budget policy
                        const policy: BudgetPolicy = {
                            id: `policy-${Date.now()}-${Math.random()}`,
                            environment: 'prod',
                            limits: {
                                total: budgetLimit,
                                currency: 'GBP',
                                duration: '72h',
                            },
                            enforcement: {
                                mode: 'block',
                                warningThreshold: 0.8,
                            },
                        };

                        // Load policy into agent
                        agent['budgetPolicies'].set(policy.id, policy);

                        // Track existing costs
                        let totalExistingCost = 0;
                        for (const cost of existingCosts) {
                            await agent.trackCostOperation(
                                'GameLift',
                                'CreateFleet',
                                cost,
                                policy.id,
                                testContext
                            );
                            totalExistingCost += cost;
                        }

                        // Check if new operation would exceed budget (BEFORE tracking it)
                        const result = await agent.checkBudget(policy.id, newOperationCost);

                        const wouldExceed = totalExistingCost + newOperationCost > budgetLimit;

                        if (wouldExceed) {
                            // Operation should be blocked
                            expect(result.allowed).toBe(false);
                            expect(result.reason).toBeDefined();
                            expect(result.reason).toContain('exceed');
                            expect(result.summary.status).toBe('exceeded');
                        } else {
                            // Operation should be allowed
                            expect(result.allowed).toBe(true);
                            expect(result.reason).toBeUndefined();
                        }

                        // Verify summary calculations (should only include existing costs, not the new operation)
                        expect(result.summary.totalCost).toBe(totalExistingCost);
                        expect(result.summary.remainingBudget).toBe(budgetLimit - totalExistingCost);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should block operations that would exceed per-service budget limits', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 100, max: 500 }), // Service limit
                    fc.array(fc.integer({ min: 1, max: 50 }), { minLength: 1, maxLength: 5 }), // Existing service costs
                    fc.integer({ min: 1, max: 200 }), // New operation cost
                    async (serviceLimit, existingCosts, newOperationCost) => {
                        const policy: BudgetPolicy = {
                            id: `policy-${Date.now()}-${Math.random()}`,
                            environment: 'prod',
                            limits: {
                                total: 10000, // High total limit
                                currency: 'GBP',
                                duration: '72h',
                                perService: {
                                    GameLift: serviceLimit,
                                },
                            },
                            enforcement: {
                                mode: 'block',
                            },
                        };

                        agent['budgetPolicies'].set(policy.id, policy);

                        // Track existing GameLift costs
                        let totalServiceCost = 0;
                        for (const cost of existingCosts) {
                            await agent.trackCostOperation(
                                'GameLift',
                                'CreateFleet',
                                cost,
                                policy.id,
                                testContext
                            );
                            totalServiceCost += cost;
                        }

                        // Check if new GameLift operation would exceed service limit
                        const result = await agent.checkBudget(
                            policy.id,
                            newOperationCost,
                            'GameLift'
                        );

                        const wouldExceedService = totalServiceCost + newOperationCost > serviceLimit;

                        if (wouldExceedService) {
                            expect(result.allowed).toBe(false);
                            expect(result.reason).toBeDefined();
                            expect(result.reason).toContain('GameLift');
                            expect(result.reason).toContain('exceed');
                        } else {
                            expect(result.allowed).toBe(true);
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should allow operations in dev environment even when exceeding budget', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 100, max: 500 }), // Budget limit
                    fc.integer({ min: 600, max: 1000 }), // Operation cost (exceeds budget)
                    async (budgetLimit, operationCost) => {
                        const policy: BudgetPolicy = {
                            id: `policy-${Date.now()}-${Math.random()}`,
                            environment: 'dev',
                            limits: {
                                total: budgetLimit,
                                currency: 'GBP',
                                duration: '72h',
                            },
                            enforcement: {
                                mode: 'report', // Dev mode: report only
                            },
                        };

                        agent['budgetPolicies'].set(policy.id, policy);

                        const result = await agent.checkBudget(policy.id, operationCost);

                        // Dev environment should allow operations even when exceeding budget
                        expect(result.allowed).toBe(true);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should set warning status when approaching threshold', async () => {
            const policy: BudgetPolicy = {
                id: 'test-policy-warning',
                environment: 'prod',
                limits: {
                    total: 1000,
                    currency: 'GBP',
                    duration: '72h',
                },
                enforcement: {
                    mode: 'block',
                    warningThreshold: 0.8, // 80% threshold
                },
            };

            agent['budgetPolicies'].set(policy.id, policy);

            // Track costs up to 85% of budget
            await agent.trackCostOperation('GameLift', 'CreateFleet', 850, policy.id, testContext);

            const result = await agent.checkBudget(policy.id, 0);

            expect(result.summary.status).toBe('warning');
            expect(result.summary.totalCost).toBe(850);
            expect(result.summary.remainingBudget).toBe(150);
        });

        it('should handle multiple services with different cost patterns', async () => {
            const policy: BudgetPolicy = {
                id: 'test-policy-multi-service',
                environment: 'prod',
                limits: {
                    total: 1000,
                    currency: 'GBP',
                    duration: '72h',
                    perService: {
                        GameLift: 600,
                        Cognito: 100,
                        DynamoDB: 200,
                        Lambda: 100,
                    },
                },
                enforcement: {
                    mode: 'block',
                },
            };

            agent['budgetPolicies'].set(policy.id, policy);

            // Track costs for different services
            await agent.trackCostOperation('GameLift', 'CreateFleet', 500, policy.id, testContext);
            await agent.trackCostOperation('Cognito', 'CreateUserPool', 50, policy.id, testContext);
            await agent.trackCostOperation('DynamoDB', 'CreateTable', 150, policy.id, testContext);

            // Try to add more GameLift cost (would exceed service limit)
            const result1 = await agent.checkBudget(policy.id, 150, 'GameLift');
            expect(result1.allowed).toBe(false);
            expect(result1.reason).toContain('GameLift');

            // Try to add Lambda cost (within limits)
            const result2 = await agent.checkBudget(policy.id, 50, 'Lambda');
            expect(result2.allowed).toBe(true);

            // Verify service breakdown
            const summary = await agent.generateCostSummary(policy.id);
            expect(summary.byService['GameLift']).toBe(500);
            expect(summary.byService['Cognito']).toBe(50);
            expect(summary.byService['DynamoDB']).toBe(150);
            expect(summary.totalCost).toBe(700);
        });

        it('should handle edge case: zero cost operations', async () => {
            const policy: BudgetPolicy = {
                id: 'test-policy-zero',
                environment: 'prod',
                limits: {
                    total: 1000,
                    currency: 'GBP',
                    duration: '72h',
                },
                enforcement: {
                    mode: 'block',
                },
            };

            agent['budgetPolicies'].set(policy.id, policy);

            const result = await agent.checkBudget(policy.id, 0);

            expect(result.allowed).toBe(true);
            expect(result.summary.totalCost).toBe(0);
            expect(result.summary.remainingBudget).toBe(1000);
        });

        it('should handle edge case: exact budget limit', async () => {
            const policy: BudgetPolicy = {
                id: 'test-policy-exact',
                environment: 'prod',
                limits: {
                    total: 1000,
                    currency: 'GBP',
                    duration: '72h',
                },
                enforcement: {
                    mode: 'block',
                },
            };

            agent['budgetPolicies'].set(policy.id, policy);

            // Track costs up to exact budget
            await agent.trackCostOperation('GameLift', 'CreateFleet', 1000, policy.id, testContext);

            // Try to add any additional cost
            const result = await agent.checkBudget(policy.id, 1);

            expect(result.allowed).toBe(false);
            expect(result.reason).toContain('exceed');
        });
    });
});
