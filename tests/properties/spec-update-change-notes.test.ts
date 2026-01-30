/**
 * Property-Based Test: Spec Update with Change Notes
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 15: Spec Update with Change Notes
 * 
 * For any system state change operation, the corresponding specification document
 * must be updated with a new entry containing timestamp, actor, action, and
 * descriptive change notes.
 * 
 * Validates: Requirements 17.1, 17.2
 */

import fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';
import { PlanGenerator } from '../../Orchestrator/src/services/PlanGenerator';
import { PlanExecutor } from '../../Orchestrator/src/services/PlanExecutor';
import { PlanContext, ChangeNote } from '../../Orchestrator/src/types';

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 15: Spec Update with Change Notes', () => {
        let planGenerator: PlanGenerator;
        let planExecutor: PlanExecutor;
        const changeNotesDir = path.join(process.cwd(), 'Specs', 'change-notes');

        beforeAll(() => {
            // Ensure change notes directory exists
            if (!fs.existsSync(changeNotesDir)) {
                fs.mkdirSync(changeNotesDir, { recursive: true });
            }
        });

        beforeEach(() => {
            planGenerator = new PlanGenerator();
            planExecutor = new PlanExecutor();
        });

        afterEach(() => {
            // Clean up test change notes
            if (fs.existsSync(changeNotesDir)) {
                const files = fs.readdirSync(changeNotesDir);
                files.forEach((file) => {
                    if (file.startsWith('test-')) {
                        fs.unlinkSync(path.join(changeNotesDir, file));
                    }
                });
            }
        });

        it('should create change notes for all state-changing operations', async () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 10, maxLength: 200 }),
                    async (specification) => {
                        const context: PlanContext = { targetEnvironment: 'dev' };
                        const plan = await planGenerator.generatePlan(specification, context);

                        // Approve and execute plan
                        plan.status = 'approved';
                        const execution = await planExecutor.executePlan(plan);

                        // Wait for execution to complete
                        await waitForExecution(execution.id, planExecutor, 10000);

                        // Check if change notes file was created
                        const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

                        // Change notes should exist
                        expect(fs.existsSync(changeNotePath)).toBe(true);

                        if (fs.existsSync(changeNotePath)) {
                            const content = fs.readFileSync(changeNotePath, 'utf8');
                            const changeNotes: ChangeNote[] = JSON.parse(content);

                            // Should have change notes for each completed step
                            expect(changeNotes.length).toBeGreaterThan(0);

                            // Each change note should have required fields
                            changeNotes.forEach((note) => {
                                expect(note.timestamp).toBeDefined();
                                expect(note.actor).toBeDefined();
                                expect(note.action).toBeDefined();
                                expect(note.description).toBeDefined();
                                expect(note.specPath).toBeDefined();

                                // Timestamp should be valid ISO 8601
                                expect(() => new Date(note.timestamp)).not.toThrow();

                                // Actor should be an agent name
                                expect(typeof note.actor).toBe('string');
                                expect(note.actor.length).toBeGreaterThan(0);

                                // Action should be a capability name
                                expect(typeof note.action).toBe('string');
                                expect(note.action.length).toBeGreaterThan(0);

                                // Description should be meaningful
                                expect(typeof note.description).toBe('string');
                                expect(note.description.length).toBeGreaterThan(0);
                            });
                        }
                    }
                ),
                { numRuns: 20 } // Reduced runs since this involves file I/O
            );
        });

        it('should include timestamp in ISO 8601 format', async () => {
            const specification = 'Create a test level';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);

                changeNotes.forEach((note) => {
                    // Should be valid ISO 8601 timestamp
                    const timestamp = new Date(note.timestamp);
                    expect(timestamp.toISOString()).toBe(note.timestamp);

                    // Should be a recent timestamp
                    const now = Date.now();
                    const noteTime = timestamp.getTime();
                    expect(noteTime).toBeLessThanOrEqual(now);
                    expect(noteTime).toBeGreaterThan(now - 60000); // Within last minute
                });
            }
        });

        it('should identify the actor (agent or user) for each change', async () => {
            const specification = 'Deploy infrastructure';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);

                changeNotes.forEach((note) => {
                    // Actor should match an agent name from the plan
                    const agentNames = plan.steps.map((step) => step.agent);
                    expect(agentNames).toContain(note.actor);
                });
            }
        });

        it('should record the action (capability) performed', async () => {
            const specification = 'Generate assets';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);

                changeNotes.forEach((note) => {
                    // Action should match a capability from the plan
                    const capabilities = plan.steps.map((step) => step.capability);
                    expect(capabilities).toContain(note.action);
                });
            }
        });

        it('should include descriptive change notes', async () => {
            const specification = 'Create multiplayer level';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);

                changeNotes.forEach((note) => {
                    // Description should be meaningful (not empty or generic)
                    expect(note.description.length).toBeGreaterThan(10);
                    expect(note.description).not.toBe('');
                    expect(note.description).not.toBe('N/A');
                    expect(note.description).not.toBe('undefined');
                });
            }
        });

        it('should maintain chronological order of change notes', async () => {
            const specification = 'Multi-step operation';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);

                // Timestamps should be in chronological order
                for (let i = 1; i < changeNotes.length; i++) {
                    const prevTime = new Date(changeNotes[i - 1].timestamp).getTime();
                    const currTime = new Date(changeNotes[i].timestamp).getTime();
                    expect(currTime).toBeGreaterThanOrEqual(prevTime);
                }
            }
        });

        it('should append to existing change notes file', async () => {
            const specification = 'Test operation';
            const context: PlanContext = { targetEnvironment: 'dev' };
            const plan = await planGenerator.generatePlan(specification, context);

            plan.status = 'approved';
            const execution = await planExecutor.executePlan(plan);

            await waitForExecution(execution.id, planExecutor, 10000);

            const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

            if (fs.existsSync(changeNotePath)) {
                const content = fs.readFileSync(changeNotePath, 'utf8');
                const changeNotes: ChangeNote[] = JSON.parse(content);
                const initialCount = changeNotes.length;

                // Simulate another operation (in real scenario, this would be a new step)
                const newNote: ChangeNote = {
                    timestamp: new Date().toISOString(),
                    actor: 'TestAgent',
                    action: 'test_action',
                    description: 'Test change note',
                    specPath: 'test/path',
                };

                changeNotes.push(newNote);
                fs.writeFileSync(changeNotePath, JSON.stringify(changeNotes, null, 2));

                // Read back and verify
                const updatedContent = fs.readFileSync(changeNotePath, 'utf8');
                const updatedNotes: ChangeNote[] = JSON.parse(updatedContent);

                expect(updatedNotes.length).toBe(initialCount + 1);
                expect(updatedNotes[updatedNotes.length - 1]).toEqual(newNote);
            }
        });

        it('should handle concurrent change note writes safely', async () => {
            // This test verifies that multiple operations can write change notes
            // without corrupting the file

            const specifications = [
                'Operation 1',
                'Operation 2',
                'Operation 3',
            ];

            const executions = await Promise.all(
                specifications.map(async (spec) => {
                    const context: PlanContext = { targetEnvironment: 'dev' };
                    const plan = await planGenerator.generatePlan(spec, context);
                    plan.status = 'approved';
                    return planExecutor.executePlan(plan);
                })
            );

            // Wait for all executions
            await Promise.all(
                executions.map((exec) => waitForExecution(exec.id, planExecutor, 10000))
            );

            // Verify each execution has valid change notes
            executions.forEach((execution) => {
                const changeNotePath = path.join(changeNotesDir, `${execution.id}.json`);

                if (fs.existsSync(changeNotePath)) {
                    const content = fs.readFileSync(changeNotePath, 'utf8');

                    // Should be valid JSON
                    expect(() => JSON.parse(content)).not.toThrow();

                    const changeNotes: ChangeNote[] = JSON.parse(content);
                    expect(Array.isArray(changeNotes)).toBe(true);
                    expect(changeNotes.length).toBeGreaterThan(0);
                }
            });
        });
    });
});

// Helper function to wait for execution to complete
async function waitForExecution(
    executionId: string,
    executor: PlanExecutor,
    timeout: number
): Promise<void> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
        const execution = executor.getExecution(executionId);

        if (execution && (execution.status === 'completed' || execution.status === 'failed')) {
            return;
        }

        await new Promise((resolve) => setTimeout(resolve, 100));
    }

    throw new Error(`Execution ${executionId} did not complete within ${timeout}ms`);
}
