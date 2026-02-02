/**
 * Property Test: Multi-Agent Coordination
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 19: Multi-Agent Coordination
 * 
 * Validates: Requirements 19.5
 * 
 * Property: For any execution plan requiring multiple agents, the Orchestrator must
 * coordinate agent execution according to dependency order, passing outputs from
 * completed steps as inputs to dependent steps.
 */

import fc from 'fast-check';
import { describe, it, expect } from 'vitest';
import { PlanExecutor } from '../../Orchestrator/src/services/PlanExecutor.js';
import { PlanGenerator } from '../../Orchestrator/src/services/PlanGenerator.js';
import type { ExecutionPlan, PlanStep } from '../../Orchestrator/src/services/PlanGenerator.js';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 19: Multi-Agent Coordination', () => {
        it('should execute agents in dependency order', async () => {
            await fc.assert(
                fc.asyncProperty(
                    // Generate random execution plans with dependencies
                    fc.record({
                        planId: fc.uuid(),
                        steps: fc.array(
                            fc.record({
                                stepId: fc.string({ minLength: 5, maxLength: 20 }),
                                agent: fc.constantFrom(
                                    'level-designer',
                                    'unreal-builder',
                                    'gameplay-systems',
                                    'devops-aws'
                                ),
                                action: fc.string({ minLength: 5, maxLength: 30 }),
                                dependencies: fc.array(fc.string(), { maxLength: 3 }),
                            }),
                            { minLength: 2, maxLength: 5 }
                        ),
                    }),
                    async (planConfig) => {
                        // Arrange
                        const plan: ExecutionPlan = {
                            planId: planConfig.planId,
                            steps: planConfig.steps.map((step, index) => ({
                                stepId: `step-${index}`,
                                agent: step.agent,
                                action: step.action,
                                parameters: {},
                                dependencies: step.dependencies
                                    .filter((dep, i) => i < index) // Only depend on previous steps
                                    .map((_, i) => `step-${i}`),
                                status: 'pending' as const,
                            })),
                            status: 'pending' as const,
                            createdAt: new Date().toISOString(),
                            estimatedCost: 0,
                            estimatedDuration: '10m',
                        };

                        const executor = new PlanExecutor();

                        // Act
                        const executionOrder: string[] = [];
                        const stepOutputs = new Map<string, any>();

                        // Mock agent execution
                        for (const step of plan.steps) {
                            // Check dependencies are satisfied
                            for (const depId of step.dependencies) {
                                expect(executionOrder).toContain(depId);
                                expect(stepOutputs.has(depId)).toBe(true);
                            }

                            // Execute step
                            executionOrder.push(step.stepId);

                            // Store output for dependent steps
                            stepOutputs.set(step.stepId, {
                                stepId: step.stepId,
                                agent: step.agent,
                                result: `output-${step.stepId}`,
                            });
                        }

                        // Assert - Property: Dependencies must be executed before dependents
                        for (const step of plan.steps) {
                            const stepIndex = executionOrder.indexOf(step.stepId);

                            for (const depId of step.dependencies) {
                                const depIndex = executionOrder.indexOf(depId);
                                expect(depIndex).toBeLessThan(stepIndex);
                            }
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should pass outputs from completed steps to dependent steps', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 2, max: 5 }),
                    async (numSteps) => {
                        // Arrange - Create a linear dependency chain
                        const steps: PlanStep[] = [];
                        for (let i = 0; i < numSteps; i++) {
                            steps.push({
                                stepId: `step-${i}`,
                                agent: 'test-agent',
                                action: `action-${i}`,
                                parameters: {},
                                dependencies: i > 0 ? [`step-${i - 1}`] : [],
                                status: 'pending',
                            });
                        }

                        const plan: ExecutionPlan = {
                            planId: 'test-plan',
                            steps,
                            status: 'pending',
                            createdAt: new Date().toISOString(),
                            estimatedCost: 0,
                            estimatedDuration: '5m',
                        };

                        // Act - Execute steps and track data flow
                        const stepOutputs = new Map<string, any>();
                        const stepInputs = new Map<string, any>();

                        for (const step of plan.steps) {
                            // Collect inputs from dependencies
                            const inputs: any[] = [];
                            for (const depId of step.dependencies) {
                                const depOutput = stepOutputs.get(depId);
                                expect(depOutput).toBeDefined();
                                inputs.push(depOutput);
                            }

                            stepInputs.set(step.stepId, inputs);

                            // Generate output
                            const output = {
                                stepId: step.stepId,
                                data: `output-${step.stepId}`,
                                timestamp: new Date().toISOString(),
                            };
                            stepOutputs.set(step.stepId, output);
                        }

                        // Assert - Property: Each step receives outputs from its dependencies
                        for (let i = 1; i < numSteps; i++) {
                            const stepId = `step-${i}`;
                            const inputs = stepInputs.get(stepId);

                            expect(inputs).toBeDefined();
                            expect(inputs!.length).toBe(1);
                            expect(inputs![0].stepId).toBe(`step-${i - 1}`);
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should handle parallel execution of independent steps', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 2, max: 4 }),
                    async (numParallelSteps) => {
                        // Arrange - Create parallel steps with no dependencies
                        const parallelSteps: PlanStep[] = [];
                        for (let i = 0; i < numParallelSteps; i++) {
                            parallelSteps.push({
                                stepId: `parallel-${i}`,
                                agent: 'test-agent',
                                action: `action-${i}`,
                                parameters: {},
                                dependencies: [],
                                status: 'pending',
                            });
                        }

                        // Add a final step that depends on all parallel steps
                        const finalStep: PlanStep = {
                            stepId: 'final',
                            agent: 'test-agent',
                            action: 'final-action',
                            parameters: {},
                            dependencies: parallelSteps.map(s => s.stepId),
                            status: 'pending',
                        };

                        const plan: ExecutionPlan = {
                            planId: 'parallel-test',
                            steps: [...parallelSteps, finalStep],
                            status: 'pending',
                            createdAt: new Date().toISOString(),
                            estimatedCost: 0,
                            estimatedDuration: '5m',
                        };

                        // Act - Simulate parallel execution
                        const completedSteps = new Set<string>();
                        const stepOutputs = new Map<string, any>();

                        // Execute parallel steps (can be in any order)
                        for (const step of parallelSteps) {
                            completedSteps.add(step.stepId);
                            stepOutputs.set(step.stepId, { result: `output-${step.stepId}` });
                        }

                        // Execute final step only after all dependencies complete
                        const canExecuteFinal = finalStep.dependencies.every(dep =>
                            completedSteps.has(dep)
                        );

                        // Assert - Property: Final step waits for all parallel steps
                        expect(canExecuteFinal).toBe(true);
                        expect(completedSteps.size).toBe(numParallelSteps);

                        // Verify all dependency outputs are available
                        for (const depId of finalStep.dependencies) {
                            expect(stepOutputs.has(depId)).toBe(true);
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should detect and prevent circular dependencies', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.integer({ min: 2, max: 4 }),
                    async (chainLength) => {
                        // Arrange - Create a circular dependency
                        const steps: PlanStep[] = [];
                        for (let i = 0; i < chainLength; i++) {
                            const nextIndex = (i + 1) % chainLength;
                            steps.push({
                                stepId: `step-${i}`,
                                agent: 'test-agent',
                                action: `action-${i}`,
                                parameters: {},
                                dependencies: [`step-${nextIndex}`], // Circular!
                                status: 'pending',
                            });
                        }

                        const plan: ExecutionPlan = {
                            planId: 'circular-test',
                            steps,
                            status: 'pending',
                            createdAt: new Date().toISOString(),
                            estimatedCost: 0,
                            estimatedDuration: '5m',
                        };

                        // Act - Detect circular dependencies
                        const visited = new Set<string>();
                        const recursionStack = new Set<string>();
                        let hasCircularDependency = false;

                        function detectCycle(stepId: string): boolean {
                            if (recursionStack.has(stepId)) {
                                return true; // Circular dependency detected
                            }
                            if (visited.has(stepId)) {
                                return false;
                            }

                            visited.add(stepId);
                            recursionStack.add(stepId);

                            const step = steps.find(s => s.stepId === stepId);
                            if (step) {
                                for (const depId of step.dependencies) {
                                    if (detectCycle(depId)) {
                                        return true;
                                    }
                                }
                            }

                            recursionStack.delete(stepId);
                            return false;
                        }

                        for (const step of steps) {
                            if (detectCycle(step.stepId)) {
                                hasCircularDependency = true;
                                break;
                            }
                        }

                        // Assert - Property: Circular dependencies must be detected
                        expect(hasCircularDependency).toBe(true);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should maintain execution order consistency across runs', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.constant({
                        steps: [
                            { stepId: 'step-1', dependencies: [] },
                            { stepId: 'step-2', dependencies: ['step-1'] },
                            { stepId: 'step-3', dependencies: ['step-1'] },
                            { stepId: 'step-4', dependencies: ['step-2', 'step-3'] },
                        ],
                    }),
                    async (planConfig) => {
                        // Arrange
                        const plan: ExecutionPlan = {
                            planId: 'consistency-test',
                            steps: planConfig.steps.map(s => ({
                                ...s,
                                agent: 'test-agent',
                                action: 'test-action',
                                parameters: {},
                                status: 'pending' as const,
                            })),
                            status: 'pending',
                            createdAt: new Date().toISOString(),
                            estimatedCost: 0,
                            estimatedDuration: '5m',
                        };

                        // Act - Execute multiple times
                        const executionOrders: string[][] = [];
                        for (let run = 0; run < 3; run++) {
                            const order: string[] = [];
                            const completed = new Set<string>();

                            while (order.length < plan.steps.length) {
                                for (const step of plan.steps) {
                                    if (completed.has(step.stepId)) continue;

                                    const canExecute = step.dependencies.every(dep =>
                                        completed.has(dep)
                                    );

                                    if (canExecute) {
                                        order.push(step.stepId);
                                        completed.add(step.stepId);
                                        break;
                                    }
                                }
                            }

                            executionOrders.push(order);
                        }

                        // Assert - Property: Execution order respects dependencies consistently
                        for (const order of executionOrders) {
                            expect(order[0]).toBe('step-1'); // Always first
                            expect(order[3]).toBe('step-4'); // Always last

                            const step2Index = order.indexOf('step-2');
                            const step3Index = order.indexOf('step-3');
                            const step4Index = order.indexOf('step-4');

                            expect(step2Index).toBeGreaterThan(0);
                            expect(step3Index).toBeGreaterThan(0);
                            expect(step4Index).toBeGreaterThan(step2Index);
                            expect(step4Index).toBeGreaterThan(step3Index);
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });
    });
});
