/**
 * CostMonitorFinOpsAgent
 * 
 * MANDATORY agent responsible for:
 * - Cost tracking for AWS operations
 * - Budget policy enforcement
 * - Cost reporting and warnings
 * - Preventing budget overruns
 * 
 * This agent ensures the system stays within budget limits and provides
 * real-time cost monitoring and enforcement.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';
import * as fs from 'fs/promises';
import { getEnvironmentManager, type Environment } from '../Orchestrator/src/services/EnvironmentManager.js';

/**
 * Cost record for tracking AWS operations
 */
export interface CostRecord {
    recordId: string;
    timestamp: string;
    service: string;
    operation: string;
    cost: number;
    currency: string;
    resourceId?: string;
    tags: Record<string, string>;
    budgetPolicyId: string;
}

/**
 * Cost summary with budget tracking
 */
export interface CostSummary {
    budgetPolicyId: string;
    totalCost: number;
    currency: string;
    startTime: string;
    endTime: string;
    byService: Record<string, number>;
    projectedTotal: number;
    remainingBudget: number;
    status: 'ok' | 'warning' | 'exceeded';
}

/**
 * Budget policy structure
 */
export interface BudgetPolicy {
    id: string;
    environment: 'dev' | 'prod';
    limits: {
        total: number;
        currency: string;
        duration: string;
        perService?: Record<string, number>;
    };
    enforcement: {
        mode: 'report' | 'warn' | 'block';
        warningThreshold?: number;
        approvalRequired?: boolean;
    };
}

export class CostMonitorFinOpsAgent extends BaseAgent {
    private costRecords: Map<string, CostRecord[]>;
    private budgetPolicies: Map<string, BudgetPolicy>;
    private environmentManager = getEnvironmentManager();

    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'cost-monitor-finops',
            description:
                'MANDATORY agent for cost monitoring, budget enforcement, and financial governance',
            capabilities: [
                {
                    name: 'track_cost',
                    description:
                        'Track cost for an AWS operation with service, operation, and resource details',
                    parameters: {
                        type: 'object',
                        required: ['service', 'operation', 'cost', 'budgetPolicyId'],
                        properties: {
                            service: {
                                type: 'string',
                                description: 'AWS service name (GameLift, Cognito, DynamoDB, Lambda)',
                            },
                            operation: {
                                type: 'string',
                                description: 'Operation performed',
                            },
                            cost: {
                                type: 'number',
                                description: 'Estimated cost in GBP',
                            },
                            currency: {
                                type: 'string',
                                description: 'Currency code (default: GBP)',
                            },
                            resourceId: {
                                type: 'string',
                                description: 'AWS resource ID',
                            },
                            tags: {
                                type: 'object',
                                description: 'Resource tags for cost allocation',
                            },
                            budgetPolicyId: {
                                type: 'string',
                                description: 'Budget policy ID to track against',
                            },
                        },
                    },
                    mcpAdapters: ['AWSMCP'],
                },
                {
                    name: 'check_budget',
                    description:
                        'Check if an operation would exceed budget limits before execution',
                    parameters: {
                        type: 'object',
                        required: ['budgetPolicyId', 'estimatedCost'],
                        properties: {
                            budgetPolicyId: {
                                type: 'string',
                                description: 'Budget policy ID to check against',
                            },
                            estimatedCost: {
                                type: 'number',
                                description: 'Estimated cost of the operation',
                            },
                            service: {
                                type: 'string',
                                description: 'Service for per-service budget checking',
                            },
                        },
                    },
                },
                {
                    name: 'generate_cost_report',
                    description:
                        'Generate a cost summary report with breakdown by service and budget status',
                    parameters: {
                        type: 'object',
                        required: ['budgetPolicyId'],
                        properties: {
                            budgetPolicyId: {
                                type: 'string',
                                description: 'Budget policy ID to report on',
                            },
                            startTime: {
                                type: 'string',
                                description: 'Start time for report (ISO 8601)',
                            },
                            endTime: {
                                type: 'string',
                                description: 'End time for report (ISO 8601)',
                            },
                        },
                    },
                },
                {
                    name: 'load_budget_policy',
                    description: 'Load and validate a budget policy from file',
                    parameters: {
                        type: 'object',
                        required: ['policyPath'],
                        properties: {
                            policyPath: {
                                type: 'string',
                                description: 'Path to BudgetPolicy.json file',
                            },
                        },
                    },
                    mcpAdapters: ['GitHubMCP'],
                },
                {
                    name: 'issue_warning',
                    description:
                        'Issue a cost warning when approaching budget threshold',
                    parameters: {
                        type: 'object',
                        required: ['budgetPolicyId', 'currentCost', 'threshold'],
                        properties: {
                            budgetPolicyId: {
                                type: 'string',
                                description: 'Budget policy ID',
                            },
                            currentCost: {
                                type: 'number',
                                description: 'Current accumulated cost',
                            },
                            threshold: {
                                type: 'number',
                                description: 'Warning threshold percentage (0-1)',
                            },
                        },
                    },
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
                region: 'eu-west-1',
                temperature: 0.1, // Very low temperature for consistent cost calculations
            },
        };

        super(config, mcpAdapters);
        this.costRecords = new Map();
        this.budgetPolicies = new Map();
    }

    protected getSystemPrompt(): string {
        return `You are the CostMonitorFinOpsAgent, a MANDATORY financial governance agent responsible for preventing budget overruns.

Your responsibilities:

1. **Cost Tracking**: Record all AWS operation costs:
   - Track costs per service (GameLift, Cognito, DynamoDB, Lambda)
   - Store cost records with timestamps and resource IDs
   - Maintain accurate cost history
   - Tag costs for allocation and reporting

2. **Budget Enforcement**: Prevent budget overruns:
   - Load and validate BudgetPolicy.schema.json
   - Check costs against limits BEFORE operations
   - Block operations that would exceed budget
   - Enforce per-service budget limits
   - Respect environment-specific enforcement modes

3. **Cost Reporting**: Generate comprehensive reports:
   - Cost summaries with service breakdowns
   - Budget status (ok, warning, exceeded)
   - Projected costs for 72h events
   - Remaining budget calculations
   - Cost trends and anomalies

4. **Warning System**: Issue proactive warnings:
   - Alert at threshold percentages (default 80%)
   - Notify stakeholders of approaching limits
   - Recommend cost optimization actions
   - Track warning history

Key Principles:
- ALWAYS check budget before approving operations
- NEVER allow operations that exceed budget limits
- Be conservative with cost estimates
- Default budget: £1000 for 72-hour events
- Enforcement modes:
  - dev: report only, allow operations
  - prod: block operations that exceed budget
- Track costs in real-time, not retrospectively

Output Format:
Return structured JSON with:
- Cost records with all required fields
- Budget status (ok/warning/exceeded)
- Remaining budget
- Recommendations for cost optimization

Be strict, accurate, and proactive in cost governance.`;
    }

    /**
     * Track cost for an AWS operation
     */
    async trackCostOperation(
        service: string,
        operation: string,
        cost: number,
        budgetPolicyId: string,
        _context: AgentContext,
        options?: {
            currency?: string;
            resourceId?: string;
            tags?: Record<string, string>;
        }
    ): Promise<AgentResult> {
        const record: CostRecord = {
            recordId: `cost-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date().toISOString(),
            service,
            operation,
            cost,
            currency: options?.currency || 'GBP',
            resourceId: options?.resourceId,
            tags: options?.tags || {},
            budgetPolicyId,
        };

        // Store cost record
        if (!this.costRecords.has(budgetPolicyId)) {
            this.costRecords.set(budgetPolicyId, []);
        }
        this.costRecords.get(budgetPolicyId)!.push(record);

        // Track cost internally using parent class method
        super.trackCost(service, operation, cost, options?.currency || 'GBP');

        return {
            success: true,
            result: {
                record,
                message: `Cost tracked: ${service} ${operation} - £${cost.toFixed(2)}`,
            },
            duration: 0,
        };
    }

    /**
     * Check if an operation would exceed budget
     */
    async checkBudget(
        budgetPolicyId: string,
        estimatedCost: number,
        service?: string
    ): Promise<{ allowed: boolean; reason?: string; summary: CostSummary }> {
        const policy = this.budgetPolicies.get(budgetPolicyId);
        if (!policy) {
            throw new Error(`Budget policy not found: ${budgetPolicyId}`);
        }

        const summary = await this.generateCostSummary(budgetPolicyId);
        const projectedCost = summary.totalCost + estimatedCost;

        // Check total budget
        if (projectedCost > policy.limits.total) {
            summary.status = 'exceeded';
            if (policy.enforcement.mode === 'block') {
                return {
                    allowed: false,
                    reason: `Operation would exceed total budget: £${projectedCost.toFixed(2)} > £${policy.limits.total}`,
                    summary,
                };
            }
        }

        // Check per-service budget if specified
        if (service && policy.limits.perService?.[service]) {
            const serviceLimit = policy.limits.perService[service];
            const serviceCost = (summary.byService[service] || 0) + estimatedCost;
            if (serviceCost > serviceLimit) {
                if (policy.enforcement.mode === 'block') {
                    return {
                        allowed: false,
                        reason: `Operation would exceed ${service} budget: £${serviceCost.toFixed(2)} > £${serviceLimit}`,
                        summary,
                    };
                }
            }
        }

        // Check warning threshold
        const threshold = policy.enforcement.warningThreshold || 0.8;
        if (projectedCost > policy.limits.total * threshold) {
            summary.status = 'warning';
        }

        return {
            allowed: true,
            summary,
        };
    }

    /**
     * Generate cost summary for a budget policy
     */
    async generateCostSummary(budgetPolicyId: string): Promise<CostSummary> {
        const policy = this.budgetPolicies.get(budgetPolicyId);
        if (!policy) {
            throw new Error(`Budget policy not found: ${budgetPolicyId}`);
        }

        const records = this.costRecords.get(budgetPolicyId) || [];
        const now = new Date();

        // Calculate total cost
        const totalCost = records.reduce((sum, record) => sum + record.cost, 0);

        // Calculate cost by service
        const byService: Record<string, number> = {};
        for (const record of records) {
            byService[record.service] = (byService[record.service] || 0) + record.cost;
        }

        // Calculate projected total (simple linear projection)
        const durationHours = this.parseDuration(policy.limits.duration);
        const elapsedHours = records.length > 0
            ? (now.getTime() - new Date(records[0].timestamp).getTime()) / (1000 * 60 * 60)
            : 0;
        const projectedTotal = elapsedHours > 0
            ? (totalCost / elapsedHours) * durationHours
            : totalCost;

        // Determine status
        let status: 'ok' | 'warning' | 'exceeded' = 'ok';
        if (totalCost > policy.limits.total) {
            status = 'exceeded';
        } else if (totalCost > policy.limits.total * (policy.enforcement.warningThreshold || 0.8)) {
            status = 'warning';
        }

        return {
            budgetPolicyId,
            totalCost,
            currency: policy.limits.currency,
            startTime: records.length > 0 ? records[0].timestamp : now.toISOString(),
            endTime: now.toISOString(),
            byService,
            projectedTotal,
            remainingBudget: policy.limits.total - totalCost,
            status,
        };
    }

    /**
     * Load budget policy from file
     */
    async loadBudgetPolicy(policyPath: string): Promise<BudgetPolicy> {
        try {
            const content = await fs.readFile(policyPath, 'utf-8');
            const policy: BudgetPolicy = JSON.parse(content);

            // Validate policy structure
            if (!policy.id || !policy.environment || !policy.limits || !policy.enforcement) {
                throw new Error('Invalid budget policy structure');
            }

            // Validate policy matches current environment
            const currentEnv = this.environmentManager.getEnvironment();
            if (policy.environment !== currentEnv) {
                console.warn(
                    `Budget policy environment (${policy.environment}) does not match current environment (${currentEnv})`
                );
            }

            // Store policy
            this.budgetPolicies.set(policy.id, policy);

            return policy;
        } catch (error) {
            throw new Error(`Failed to load budget policy: ${error}`);
        }
    }

    /**
     * Get current environment
     */
    getCurrentEnvironment(): Environment {
        return this.environmentManager.getEnvironment();
    }

    /**
     * Detect and set environment
     */
    async detectEnvironment(): Promise<Environment> {
        return await this.environmentManager.detectEnvironment();
    }

    /**
     * Parse duration string (e.g., "72h") to hours
     */
    private parseDuration(duration: string): number {
        const match = duration.match(/^(\d+)h$/);
        if (!match) {
            throw new Error(`Invalid duration format: ${duration}`);
        }
        return parseInt(match[1], 10);
    }

    /**
     * Get all cost records for a budget policy
     */
    getCostRecords(budgetPolicyId: string): CostRecord[] {
        return this.costRecords.get(budgetPolicyId) || [];
    }

    /**
     * Clear cost records (for testing)
     */
    clearCostRecords(budgetPolicyId?: string): void {
        if (budgetPolicyId) {
            this.costRecords.delete(budgetPolicyId);
        } else {
            this.costRecords.clear();
        }
    }
}
