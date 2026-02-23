/**
 * Property Test: Environment-Based Approval Gates
 * Feature: unreal-vr-multiplayer-system
 * Property 11: Environment-Based Approval Gates
 *
 * Validates: Requirements 7.1, 7.2, 7.3, 7.4
 *
 * For any infrastructure change, deployment, or budget increase operation in
 * production environment, the operation must block and wait for manual approval
 * before proceeding, while the same operations in development environment must
 * proceed autonomously.
 */

import fc from 'fast-check';
import {
    getEnvironmentManager,
    resetEnvironmentManager,
    type Environment
} from '../../Orchestrator/src/services/EnvironmentManager.js';
import {
    getApprovalGateManager,
    resetApprovalGateManager,
    type OperationType
} from '../../Orchestrator/src/services/ApprovalGateManager.js';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 11: Environment-Based Approval Gates', () => {
        beforeEach(() => {
            // Reset singletons before each test
            resetEnvironmentManager();
            resetApprovalGateManager();
        });

        afterEach(() => {
            // Clean up after each test
            resetEnvironmentManager();
            resetApprovalGateManager();
        });

        it('should require approval for infrastructure changes in prod', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.constantFrom<OperationType>(
                        'infra_change',
                        'terraform_apply',
                        'gamelift_deploy',
                        'cognito_change',
                        'dynamodb_change'
                    ),
                    fc.string({ minLength: 10, maxLength: 100 }),
                    fc.string({ minLength: 5, maxLength: 20 }),
                    async (operationType, description, requestedBy) => {
                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set to production environment
                        envManager.setEnvironment('prod');

                        // Check approval gate
                        const result = await approvalManager.checkApprovalGate(
                            operationType,
                            description,
                            requestedBy
                        );

                        // Property: Operation must be blocked in prod
                        expect(result.allowed).toBe(false);
                        expect(result.requiresApproval).toBe(true);
                        expect(result.approvalRequest).toBeDefined();
                        expect(result.approvalRequest?.status).toBe('pending');
                        expect(result.approvalRequest?.operationType).toBe(operationType);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should allow autonomous operation for infrastructure changes in dev', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.constantFrom<OperationType>(
                        'infra_change',
                        'terraform_apply',
                        'gamelift_deploy',
                        'cognito_change',
                        'dynamodb_change'
                    ),
                    fc.string({ minLength: 10, maxLength: 100 }),
                    fc.string({ minLength: 5, maxLength: 20 }),
                    async (operationType, description, requestedBy) => {
                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set to development environment
                        envManager.setEnvironment('dev');

                        // Check approval gate
                        const result = await approvalManager.checkApprovalGate(
                            operationType,
                            description,
                            requestedBy
                        );

                        // Property: Operation must be allowed in dev
                        expect(result.allowed).toBe(true);
                        expect(result.requiresApproval).toBe(false);
                        expect(result.approvalRequest).toBeUndefined();
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should require approval for deployments in prod', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 10, maxLength: 100 }),
                    fc.string({ minLength: 5, maxLength: 20 }),
                    async (description, requestedBy) => {
                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set to production environment
                        envManager.setEnvironment('prod');

                        // Check approval gate for deployment
                        const result = await approvalManager.checkApprovalGate(
                            'deployment',
                            description,
                            requestedBy
                        );

                        // Property: Deployment must be blocked in prod
                        expect(result.allowed).toBe(false);
                        expect(result.requiresApproval).toBe(true);
                        expect(result.approvalRequest).toBeDefined();
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should require approval for budget increases in prod', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 10, maxLength: 100 }),
                    fc.string({ minLength: 5, maxLength: 20 }),
                    fc.integer({ min: 100, max: 10000 }),
                    async (description, requestedBy, estimatedCost) => {
                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set to production environment
                        envManager.setEnvironment('prod');

                        // Check approval gate for budget increase
                        const result = await approvalManager.checkApprovalGate(
                            'budget_increase',
                            description,
                            requestedBy,
                            { estimatedCost }
                        );

                        // Property: Budget increase must be blocked in prod
                        expect(result.allowed).toBe(false);
                        expect(result.requiresApproval).toBe(true);
                        expect(result.approvalRequest).toBeDefined();
                        expect(result.approvalRequest?.estimatedCost).toBe(estimatedCost);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should allow operations to proceed after approval', async () => {
            const envManager = getEnvironmentManager();
            const approvalManager = getApprovalGateManager();

            // Set to production environment
            envManager.setEnvironment('prod');

            // Request approval
            const result = await approvalManager.checkApprovalGate(
                'infra_change',
                'Deploy new GameLift fleet',
                'user-123'
            );

            expect(result.allowed).toBe(false);
            expect(result.approvalRequest).toBeDefined();

            const approvalId = result.approvalRequest!.id;

            // Approve the operation
            const approvedRequest = await approvalManager.approveOperation(
                approvalId,
                'admin-456'
            );

            // Property: Approved request must have correct status
            expect(approvedRequest.status).toBe('approved');
            expect(approvedRequest.approvedBy).toBe('admin-456');
            expect(approvedRequest.approvedAt).toBeDefined();

            // Property: Request should no longer be pending
            const pendingApprovals = approvalManager.getPendingApprovals();
            expect(pendingApprovals.find(r => r.id === approvalId)).toBeUndefined();
        });

        it('should block operations after rejection', async () => {
            const envManager = getEnvironmentManager();
            const approvalManager = getApprovalGateManager();

            // Set to production environment
            envManager.setEnvironment('prod');

            // Request approval
            const result = await approvalManager.checkApprovalGate(
                'deployment',
                'Deploy to production',
                'user-123'
            );

            expect(result.allowed).toBe(false);
            expect(result.approvalRequest).toBeDefined();

            const approvalId = result.approvalRequest!.id;

            // Reject the operation
            const rejectedRequest = await approvalManager.rejectOperation(
                approvalId,
                'admin-456',
                'Insufficient testing'
            );

            // Property: Rejected request must have correct status
            expect(rejectedRequest.status).toBe('rejected');
            expect(rejectedRequest.rejectedBy).toBe('admin-456');
            expect(rejectedRequest.rejectedAt).toBeDefined();
            expect(rejectedRequest.rejectionReason).toBe('Insufficient testing');

            // Property: Request should no longer be pending
            const pendingApprovals = approvalManager.getPendingApprovals();
            expect(pendingApprovals.find(r => r.id === approvalId)).toBeUndefined();
        });

        it('should maintain approval history', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.array(
                        fc.record({
                            operationType: fc.constantFrom<OperationType>(
                                'infra_change',
                                'deployment',
                                'budget_increase'
                            ),
                            description: fc.string({ minLength: 10, maxLength: 50 }),
                            requestedBy: fc.string({ minLength: 5, maxLength: 20 }),
                            shouldApprove: fc.boolean(),
                        }),
                        { minLength: 1, maxLength: 10 }
                    ),
                    async (operations) => {
                        // Reset singletons per iteration to avoid history accumulation
                        resetEnvironmentManager();
                        resetApprovalGateManager();

                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set to production environment
                        envManager.setEnvironment('prod');

                        const approvalIds: string[] = [];

                        // Create approval requests
                        for (const op of operations) {
                            const result = await approvalManager.checkApprovalGate(
                                op.operationType,
                                op.description,
                                op.requestedBy
                            );
                            if (result.approvalRequest) {
                                approvalIds.push(result.approvalRequest.id);
                            }
                        }

                        // Process approvals
                        for (let i = 0; i < approvalIds.length; i++) {
                            if (operations[i].shouldApprove) {
                                await approvalManager.approveOperation(
                                    approvalIds[i],
                                    'admin-123'
                                );
                            } else {
                                await approvalManager.rejectOperation(
                                    approvalIds[i],
                                    'admin-123',
                                    'Test rejection'
                                );
                            }
                        }

                        // Property: All requests should be in history
                        const history = approvalManager.getApprovalHistory();
                        expect(history.length).toBe(operations.length);

                        // Property: No pending approvals should remain
                        const pending = approvalManager.getPendingApprovals();
                        expect(pending.length).toBe(0);
                    }
                ),
                { numRuns: 20 }
            );
        });

        it('should enforce environment-specific behavior consistently', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.constantFrom<Environment>('dev', 'prod'),
                    fc.constantFrom<OperationType>(
                        'infra_change',
                        'deployment',
                        'budget_increase'
                    ),
                    fc.string({ minLength: 10, maxLength: 100 }),
                    fc.string({ minLength: 5, maxLength: 20 }),
                    async (environment, operationType, description, requestedBy) => {
                        const envManager = getEnvironmentManager();
                        const approvalManager = getApprovalGateManager();

                        // Set environment
                        envManager.setEnvironment(environment);

                        // Check approval gate
                        const result = await approvalManager.checkApprovalGate(
                            operationType,
                            description,
                            requestedBy
                        );

                        // Property: Behavior must match environment
                        if (environment === 'dev') {
                            expect(result.allowed).toBe(true);
                            expect(result.requiresApproval).toBe(false);
                        } else {
                            expect(result.allowed).toBe(false);
                            expect(result.requiresApproval).toBe(true);
                            expect(result.approvalRequest).toBeDefined();
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should handle concurrent approval requests', async () => {
            const envManager = getEnvironmentManager();
            const approvalManager = getApprovalGateManager();

            // Set to production environment
            envManager.setEnvironment('prod');

            // Create multiple concurrent approval requests
            const requests = await Promise.all([
                approvalManager.checkApprovalGate('infra_change', 'Change 1', 'user-1'),
                approvalManager.checkApprovalGate('deployment', 'Deploy 1', 'user-2'),
                approvalManager.checkApprovalGate('budget_increase', 'Budget 1', 'user-3'),
            ]);

            // Property: All requests should be blocked
            requests.forEach(result => {
                expect(result.allowed).toBe(false);
                expect(result.requiresApproval).toBe(true);
                expect(result.approvalRequest).toBeDefined();
            });

            // Property: All requests should be pending
            const pending = approvalManager.getPendingApprovals();
            expect(pending.length).toBe(3);

            // Property: Each request should have unique ID
            const ids = new Set(requests.map(r => r.approvalRequest!.id));
            expect(ids.size).toBe(3);
        });
    });
});
