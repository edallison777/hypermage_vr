/**
 * Plan Executor Service
 * 
 * Executes approved plans by coordinating agent actions
 */

import { v4 as uuidv4 } from 'uuid';
import {
    ExecutionPlan,
    PlanExecution,
    PlanStep,
    ChangeNote,
} from '../types';
import { logger } from '../utils/logger';
import * as fs from 'fs';
import * as path from 'path';

export class PlanExecutor {
    private executions: Map<string, PlanExecution> = new Map();

    /**
     * Execute an approved plan
     */
    public async executePlan(plan: ExecutionPlan): Promise<PlanExecution> {
        if (plan.status !== 'approved') {
            throw new Error('Plan must be approved before execution');
        }

        const executionId = uuidv4();
        const execution: PlanExecution = {
            id: executionId,
            planId: plan.id,
            startTime: new Date().toISOString(),
            status: 'running',
            progress: {
                completed: 0,
                total: plan.steps.length,
                currentStep: plan.steps[0]?.name,
            },
            steps: plan.steps.map((step) => ({
                stepId: step.id,
                planId: plan.id,
                status: 'pending',
                retryCount: 0,
            })),
            artifacts: [],
            costs: {
                totalCost: 0,
                currency: 'GBP',
                byService: {},
                byStep: {},
            },
        };

        this.executions.set(executionId, execution);

        logger.info('Starting plan execution', { executionId, planId: plan.id });

        // Execute steps asynchronously
        this.executeStepsInOrder(plan, execution).catch((error) => {
            logger.error('Plan execution failed', { executionId, error });
            execution.status = 'failed';
            execution.endTime = new Date().toISOString();
        });

        return execution;
    }

    /**
     * Get execution status
     */
    public getExecution(executionId: string): PlanExecution | undefined {
        return this.executions.get(executionId);
    }

    /**
     * Pause execution
     */
    public pauseExecution(executionId: string): void {
        const execution = this.executions.get(executionId);
        if (execution && execution.status === 'running') {
            execution.status = 'paused';
            logger.info('Execution paused', { executionId });
        }
    }

    /**
     * Resume execution
     */
    public resumeExecution(executionId: string): void {
        const execution = this.executions.get(executionId);
        if (execution && execution.status === 'paused') {
            execution.status = 'running';
            logger.info('Execution resumed', { executionId });
            // TODO: Resume from current step
        }
    }

    /**
     * Execute steps in dependency order
     */
    private async executeStepsInOrder(
        plan: ExecutionPlan,
        execution: PlanExecution
    ): Promise<void> {
        // const stepMap = new Map(plan.steps.map((step) => [step.id, step]));
        const executedSteps = new Set<string>();

        for (const step of plan.steps) {
            // Check if execution is paused
            if (execution.status === 'paused') {
                logger.info('Execution paused, waiting...', { executionId: execution.id });
                await this.waitForResume(execution);
            }

            // Check dependencies
            const dependenciesMet = step.dependencies.every((depId) => executedSteps.has(depId));
            if (!dependenciesMet) {
                logger.warn('Step dependencies not met, marking as blocked', { stepId: step.id });
                const stepExecution = execution.steps.find((s) => s.stepId === step.id);
                if (stepExecution) {
                    stepExecution.status = 'blocked';
                }
                continue;
            }

            // Execute step
            await this.executeStep(step, execution);
            executedSteps.add(step.id);

            // Update progress
            execution.progress.completed++;
            execution.progress.currentStep =
                plan.steps[execution.progress.completed]?.name || 'completed';
        }

        execution.status = 'completed';
        execution.endTime = new Date().toISOString();
        logger.info('Plan execution completed', { executionId: execution.id });
    }

    /**
     * Execute a single step
     */
    private async executeStep(step: PlanStep, execution: PlanExecution): Promise<void> {
        const stepExecution = execution.steps.find((s) => s.stepId === step.id);
        if (!stepExecution) {
            throw new Error(`Step execution not found: ${step.id}`);
        }

        stepExecution.status = 'running';
        stepExecution.startTime = new Date().toISOString();

        logger.info('Executing step', {
            stepId: step.id,
            stepName: step.name,
            agent: step.agent,
            capability: step.capability,
        });

        try {
            // TODO: Call agent via MCP adapter
            // For now, simulate execution
            await this.simulateStepExecution(step);

            stepExecution.status = 'completed';
            stepExecution.endTime = new Date().toISOString();
            stepExecution.result = { success: true };

            // Update costs
            execution.costs.totalCost += step.estimatedCost;
            execution.costs.byStep[step.id] = step.estimatedCost;

            // Update spec with change note
            await this.updateSpecWithChangeNote(step, execution);

            logger.info('Step completed', { stepId: step.id });
        } catch (error) {
            logger.error('Step failed', { stepId: step.id, error });

            stepExecution.status = 'failed';
            stepExecution.endTime = new Date().toISOString();
            stepExecution.error = {
                code: error instanceof Error ? error.name : 'UNKNOWN_ERROR',
                message: error instanceof Error ? error.message : 'Unknown error',
                details: error,
            };

            // Retry logic
            if (stepExecution.retryCount < 3) {
                stepExecution.retryCount++;
                logger.info('Retrying step', { stepId: step.id, retryCount: stepExecution.retryCount });
                await this.delay(1000 * stepExecution.retryCount);
                await this.executeStep(step, execution);
            } else {
                throw error;
            }
        }
    }

    /**
     * Simulate step execution (placeholder)
     */
    private async simulateStepExecution(_step: PlanStep): Promise<void> {
        // Simulate work with a delay
        await this.delay(Math.random() * 2000 + 1000);
    }

    /**
     * Update specification document with change note
     */
    private async updateSpecWithChangeNote(
        step: PlanStep,
        execution: PlanExecution
    ): Promise<void> {
        const changeNote: ChangeNote = {
            timestamp: new Date().toISOString(),
            actor: step.agent,
            action: step.capability,
            description: step.description,
            specPath: `executions/${execution.id}/steps/${step.id}.json`,
        };

        // Write change note to file
        const changeNotePath = path.join(
            process.cwd(),
            'Specs',
            'change-notes',
            `${execution.id}.json`
        );

        const changeNotesDir = path.dirname(changeNotePath);
        if (!fs.existsSync(changeNotesDir)) {
            fs.mkdirSync(changeNotesDir, { recursive: true });
        }

        let changeNotes: ChangeNote[] = [];
        if (fs.existsSync(changeNotePath)) {
            const content = fs.readFileSync(changeNotePath, 'utf8');
            changeNotes = JSON.parse(content);
        }

        changeNotes.push(changeNote);
        fs.writeFileSync(changeNotePath, JSON.stringify(changeNotes, null, 2));

        logger.info('Change note recorded', { changeNote });
    }

    /**
     * Wait for execution to resume
     */
    private async waitForResume(execution: PlanExecution): Promise<void> {
        while (execution.status === 'paused') {
            await this.delay(1000);
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
}
