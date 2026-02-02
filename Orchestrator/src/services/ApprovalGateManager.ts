/**
 * ApprovalGateManager
 * 
 * Manages approval gates for operations in production environment.
 * Blocks operations until manual approval is received.
 */

import { getEnvironmentManager } from './EnvironmentManager.js';

export type OperationType =
    | 'infra_change'
    | 'deployment'
    | 'budget_increase'
    | 'terraform_apply'
    | 'gamelift_deploy'
    | 'cognito_change'
    | 'dynamodb_change';

export interface ApprovalRequest {
    id: string;
    operationType: OperationType;
    description: string;
    estimatedCost?: number;
    requestedAt: string;
    requestedBy: string;
    status: 'pending' | 'approved' | 'rejected';
    approvedBy?: string;
    approvedAt?: string;
    rejectedBy?: string;
    rejectedAt?: string;
    rejectionReason?: string;
    metadata?: Record<string, any>;
}

export interface ApprovalGateResult {
    allowed: boolean;
    requiresApproval: boolean;
    approvalRequest?: ApprovalRequest;
    reason?: string;
}

export class ApprovalGateManager {
    private pendingApprovals: Map<string, ApprovalRequest>;
    private approvalHistory: ApprovalRequest[];
    private environmentManager = getEnvironmentManager();

    constructor() {
        this.pendingApprovals = new Map();
        this.approvalHistory = [];
    }

    /**
     * Check if an operation requires approval and create approval request if needed
     */
    async checkApprovalGate(
        operationType: OperationType,
        description: string,
        requestedBy: string,
        options?: {
            estimatedCost?: number;
            metadata?: Record<string, any>;
        }
    ): Promise<ApprovalGateResult> {
        const environment = this.environmentManager.getEnvironment();

        // Dev environment: allow autonomous operation
        if (environment === 'dev') {
            return {
                allowed: true,
                requiresApproval: false,
                reason: 'Development environment allows autonomous operation',
            };
        }

        // Prod environment: check if approval is required
        const requiresApproval = this.requiresApproval(operationType);

        if (!requiresApproval) {
            return {
                allowed: true,
                requiresApproval: false,
                reason: 'Operation does not require approval',
            };
        }

        // Create approval request
        const approvalRequest: ApprovalRequest = {
            id: `approval-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            operationType,
            description,
            estimatedCost: options?.estimatedCost,
            requestedAt: new Date().toISOString(),
            requestedBy,
            status: 'pending',
            metadata: options?.metadata,
        };

        this.pendingApprovals.set(approvalRequest.id, approvalRequest);

        return {
            allowed: false,
            requiresApproval: true,
            approvalRequest,
            reason: `Operation requires approval in production environment`,
        };
    }

    /**
     * Approve an operation
     */
    async approveOperation(
        approvalId: string,
        approvedBy: string
    ): Promise<ApprovalRequest> {
        const request = this.pendingApprovals.get(approvalId);

        if (!request) {
            throw new Error(`Approval request not found: ${approvalId}`);
        }

        if (request.status !== 'pending') {
            throw new Error(`Approval request is not pending: ${request.status}`);
        }

        request.status = 'approved';
        request.approvedBy = approvedBy;
        request.approvedAt = new Date().toISOString();

        this.pendingApprovals.delete(approvalId);
        this.approvalHistory.push(request);

        return request;
    }

    /**
     * Reject an operation
     */
    async rejectOperation(
        approvalId: string,
        rejectedBy: string,
        reason: string
    ): Promise<ApprovalRequest> {
        const request = this.pendingApprovals.get(approvalId);

        if (!request) {
            throw new Error(`Approval request not found: ${approvalId}`);
        }

        if (request.status !== 'pending') {
            throw new Error(`Approval request is not pending: ${request.status}`);
        }

        request.status = 'rejected';
        request.rejectedBy = rejectedBy;
        request.rejectedAt = new Date().toISOString();
        request.rejectionReason = reason;

        this.pendingApprovals.delete(approvalId);
        this.approvalHistory.push(request);

        return request;
    }

    /**
     * Get pending approval requests
     */
    getPendingApprovals(): ApprovalRequest[] {
        return Array.from(this.pendingApprovals.values());
    }

    /**
     * Get approval request by ID
     */
    getApprovalRequest(approvalId: string): ApprovalRequest | undefined {
        return this.pendingApprovals.get(approvalId) ||
            this.approvalHistory.find(r => r.id === approvalId);
    }

    /**
     * Get approval history
     */
    getApprovalHistory(limit?: number): ApprovalRequest[] {
        const history = [...this.approvalHistory].reverse();
        return limit ? history.slice(0, limit) : history;
    }

    /**
     * Wait for approval (polling-based)
     */
    async waitForApproval(
        approvalId: string,
        options?: {
            timeout?: number; // milliseconds
            pollInterval?: number; // milliseconds
        }
    ): Promise<ApprovalRequest> {
        const timeout = options?.timeout || 300000; // 5 minutes default
        const pollInterval = options?.pollInterval || 1000; // 1 second default
        const startTime = Date.now();

        while (Date.now() - startTime < timeout) {
            const request = this.getApprovalRequest(approvalId);

            if (!request) {
                throw new Error(`Approval request not found: ${approvalId}`);
            }

            if (request.status === 'approved') {
                return request;
            }

            if (request.status === 'rejected') {
                throw new Error(
                    `Operation rejected: ${request.rejectionReason || 'No reason provided'}`
                );
            }

            // Wait before polling again
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }

        throw new Error(`Approval timeout: No response received within ${timeout}ms`);
    }

    /**
     * Check if operation type requires approval
     */
    private requiresApproval(operationType: OperationType): boolean {
        const config = this.environmentManager.getConfig();

        switch (operationType) {
            case 'infra_change':
            case 'terraform_apply':
            case 'gamelift_deploy':
            case 'cognito_change':
            case 'dynamodb_change':
                return config.requireApprovalForInfraChanges;

            case 'deployment':
                return config.requireApprovalForDeployments;

            case 'budget_increase':
                return config.requireApprovalForBudgetIncreases;

            default:
                return false;
        }
    }

    /**
     * Clear all approvals (for testing)
     */
    clearApprovals(): void {
        this.pendingApprovals.clear();
        this.approvalHistory = [];
    }
}

// Singleton instance
let approvalGateManager: ApprovalGateManager | null = null;

/**
 * Get the singleton ApprovalGateManager instance
 */
export function getApprovalGateManager(): ApprovalGateManager {
    if (!approvalGateManager) {
        approvalGateManager = new ApprovalGateManager();
    }
    return approvalGateManager;
}

/**
 * Reset the singleton (for testing)
 */
export function resetApprovalGateManager(): void {
    approvalGateManager = null;
}

