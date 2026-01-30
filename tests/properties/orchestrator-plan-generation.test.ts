/**
 * Property 17: Orchestrator Plan Generation
 * 
 * For any valid natural language specification input, the Orchestrator must generate
 * an execution plan containing a list of steps, agent assignments, dependencies,
 * estimated cost, and estimated duration.
 * 
 * Validates: Requirements 19.2
 */

import fc from 'fast-check';
import { PlanGenerator } from '../../Orchestrator/src/services/PlanGenerator';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 17: Orchestrator Plan Generation', () => {
        let planGenerator: PlanGenerator;

        beforeEach(() => {
            planGenerator = new PlanGenerator();
        });

        it('should generate a valid execution plan for any natural language specification', async () => {
            await fc.assert(
                fc.asyncProperty(
                    // Generate random natural language specifications
                    fc.record({
                        specification: fc.oneof(
                            fc.constant('Create a new VR multiplayer level with combat zones'),
                            fc.constant('Design a level with 3 objectives and reward system'),
                            fc.constant('Build a multiplayer arena for 15 players'),
                            fc.constant('Generate a level plan for a capture-the-flag game mode'),
                            fc.constant('Create a level with safe zones and spawn points'),
                            fc.string({ minLength: 10, maxLength: 200 })
                        ),
                        context: fc.record({
                            targetEnvironment: fc.constantFrom('dev' as const, 'prod' as const),
                            existingLevels: fc.array(fc.string(), { maxLength: 3 }),
                            budgetPolicyPath: fc.option(fc.constant('Specs/examples/BudgetPolicy.example.json'), { nil: undefined }),
                        }),
                    }),
                    async ({ specification, context }) => {
                        // Generate plan
                        const plan = await planGenerator.generatePlan(specification, context);

                        // Property: Plan must have required fields
                        expect(plan).toBeDefined();
                        expect(plan.id).toBeDefined();
                        expect(typeof plan.id).toBe('string');
                        expect(plan.id.length).toBeGreaterThan(0);

                        // Property: Plan must have steps
                        expect(plan.steps).toBeDefined();
                        expect(Array.isArray(plan.steps)).toBe(true);
                        expect(plan.steps.length).toBeGreaterThan(0);

                        // Property: Each step must have required fields
                        for (const step of plan.steps) {
                            expect(step.id).toBeDefined();
                            expect(typeof step.id).toBe('string');

                            expect(step.name).toBeDefined();
                            expect(typeof step.name).toBe('string');

                            expect(step.description).toBeDefined();
                            expect(typeof step.description).toBe('string');

                            // Property: Each step must have an agent assignment
                            expect(step.agent).toBeDefined();
                            expect(typeof step.agent).toBe('string');
                            expect(step.agent.length).toBeGreaterThan(0);

                            // Property: Each step must have a capability
                            expect(step.capability).toBeDefined();
                            expect(typeof step.capability).toBe('string');

                            // Property: Each step must have parameters
                            expect(step.parameters).toBeDefined();
                            expect(typeof step.parameters).toBe('object');

                            // Property: Each step must have dependencies array
                            expect(step.dependencies).toBeDefined();
                            expect(Array.isArray(step.dependencies)).toBe(true);

                            // Property: Each step must have estimated duration
                            expect(step.estimatedDuration).toBeDefined();
                            expect(typeof step.estimatedDuration).toBe('number');
                            expect(step.estimatedDuration).toBeGreaterThan(0);

                            // Property: Each step must have estimated cost
                            expect(step.estimatedCost).toBeDefined();
                            expect(typeof step.estimatedCost).toBe('number');
                            expect(step.estimatedCost).toBeGreaterThanOrEqual(0);

                            // Property: Each step must have optional flag
                            expect(step.optional).toBeDefined();
                            expect(typeof step.optional).toBe('boolean');
                        }

                        // Property: Plan must have estimated cost
                        expect(plan.estimatedCost).toBeDefined();
                        expect(typeof plan.estimatedCost).toBe('number');
                        expect(plan.estimatedCost).toBeGreaterThanOrEqual(0);

                        // Property: Plan must have estimated duration
                        expect(plan.estimatedDuration).toBeDefined();
                        expect(typeof plan.estimatedDuration).toBe('number');
                        expect(plan.estimatedDuration).toBeGreaterThan(0);

                        // Property: Plan estimated cost should be sum of step costs
                        const totalStepCost = plan.steps.reduce((sum, step) => sum + step.estimatedCost, 0);
                        expect(plan.estimatedCost).toBeCloseTo(totalStepCost, 2);

                        // Property: Plan estimated duration should be at least the longest dependency chain
                        const maxStepDuration = Math.max(...plan.steps.map(s => s.estimatedDuration));
                        expect(plan.estimatedDuration).toBeGreaterThanOrEqual(maxStepDuration);

                        // Property: Dependencies must reference valid step IDs
                        const stepIds = new Set(plan.steps.map(s => s.id));
                        for (const step of plan.steps) {
                            for (const depId of step.dependencies) {
                                expect(stepIds.has(depId)).toBe(true);
                            }
                        }

                        // Property: Plan must not have circular dependencies
                        const hasCircularDependency = checkCircularDependencies(plan.steps);
                        expect(hasCircularDependency).toBe(false);
                    }
                ),
                { numRuns: 50 } // Run 50 iterations
            );
        });

        it('should generate plans with valid context propagation', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.record({
                        specification: fc.string({ minLength: 10, maxLength: 100 }),
                        context: fc.record({
                            targetEnvironment: fc.constantFrom('dev' as const, 'prod' as const),
                            existingLevels: fc.array(fc.string(), { maxLength: 5 }),
                        }),
                    }),
                    async ({ specification, context }) => {
                        const plan = await planGenerator.generatePlan(specification, context);

                        // Property: Plan must preserve context
                        expect(plan.context).toBeDefined();
                        expect(plan.context.targetEnvironment).toBe(context.targetEnvironment);

                        if (context.existingLevels) {
                            expect(plan.context.existingLevels).toEqual(context.existingLevels);
                        }
                    }
                ),
                { numRuns: 30 }
            );
        });
    });
});

/**
 * Check for circular dependencies in plan steps
 */
function checkCircularDependencies(steps: Array<{ id: string; dependencies: string[] }>): boolean {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    function hasCycle(stepId: string): boolean {
        if (recursionStack.has(stepId)) {
            return true; // Circular dependency detected
        }
        if (visited.has(stepId)) {
            return false; // Already checked this path
        }

        visited.add(stepId);
        recursionStack.add(stepId);

        const step = steps.find(s => s.id === stepId);
        if (step) {
            for (const depId of step.dependencies) {
                if (hasCycle(depId)) {
                    return true;
                }
            }
        }

        recursionStack.delete(stepId);
        return false;
    }

    for (const step of steps) {
        if (hasCycle(step.id)) {
            return true;
        }
    }

    return false;
}
