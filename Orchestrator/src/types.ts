/**
 * Core types for the Orchestrator service
 */

export interface PlanStep {
    id: string;
    name: string;
    description: string;
    agent: string;
    capability: string;
    parameters: Record<string, unknown>;
    dependencies: string[]; // Step IDs that must complete first
    estimatedDuration: number; // milliseconds
    estimatedCost: number; // GBP
    optional: boolean;
}

export interface ExecutionPlan {
    id: string;
    createdAt: string;
    specification: string; // Natural language input
    context: PlanContext;
    steps: PlanStep[];
    estimatedCost: number;
    estimatedDuration: number; // milliseconds
    status: 'pending' | 'approved' | 'rejected' | 'executing' | 'completed' | 'failed';
}

export interface PlanContext {
    existingLevels?: string[];
    budgetPolicyPath?: string;
    targetEnvironment: 'dev' | 'prod';
}

export interface StepExecution {
    stepId: string;
    planId: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked';
    startTime?: string;
    endTime?: string;
    result?: unknown;
    error?: {
        code: string;
        message: string;
        details?: unknown;
    };
    retryCount: number;
}

export interface PlanExecution {
    id: string;
    planId: string;
    startTime: string;
    endTime?: string;
    status: 'running' | 'paused' | 'completed' | 'failed';
    progress: {
        completed: number;
        total: number;
        currentStep?: string;
    };
    steps: StepExecution[];
    artifacts: Artifact[];
    costs: CostSummary;
}

export interface Artifact {
    id: string;
    type: string;
    name: string;
    path: string;
    createdAt: string;
    createdBy: string;
    metadata?: Record<string, unknown>;
}

export interface CostSummary {
    totalCost: number;
    currency: string;
    byService: Record<string, number>;
    byStep: Record<string, number>;
}

export interface ChangeNote {
    timestamp: string;
    actor: string;
    action: string;
    description: string;
    specPath: string;
    previousVersion?: string;
    newVersion?: string;
}

// API Request/Response types

export interface CreatePlanRequest {
    specification: string;
    context?: Partial<PlanContext>;
}

export interface CreatePlanResponse {
    planId: string;
    steps: PlanStep[];
    estimatedCost: number;
    estimatedDuration: string;
}

export interface ExecutePlanRequest {
    approved: boolean;
    modifications?: Partial<PlanStep>[];
}

export interface ExecutePlanResponse {
    executionId: string;
    status: 'running' | 'paused' | 'completed' | 'failed';
    progress: {
        completed: number;
        total: number;
        currentStep: string;
    };
}

export interface ExecutionStatusResponse {
    executionId: string;
    planId: string;
    status: 'running' | 'paused' | 'completed' | 'failed';
    steps: StepExecution[];
    artifacts: Artifact[];
    costs: CostSummary;
}
