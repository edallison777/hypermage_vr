/**
 * EnvironmentManager
 * 
 * Manages environment detection and approval gate enforcement.
 * Handles different rules for dev vs prod environments.
 */

import * as fs from 'fs/promises';
import * as path from 'path';

export type Environment = 'dev' | 'prod';

export interface EnvironmentConfig {
    environment: Environment;
    budgetPolicyPath?: string;
    requireApprovalForInfraChanges: boolean;
    requireApprovalForDeployments: boolean;
    requireApprovalForBudgetIncreases: boolean;
    autonomousOperation: boolean;
}

export interface BudgetPolicy {
    id: string;
    environment: Environment;
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

export class EnvironmentManager {
    private currentEnvironment: Environment;
    private config: EnvironmentConfig;
    private budgetPolicy?: BudgetPolicy;

    constructor() {
        // Default to dev environment
        this.currentEnvironment = 'dev';
        this.config = this.getDefaultConfig('dev');
    }

    /**
     * Detect environment from configuration file or environment variable
     */
    async detectEnvironment(): Promise<Environment> {
        // Priority 1: Environment variable
        const envVar = process.env.ENVIRONMENT || process.env.NODE_ENV;
        if (envVar === 'production' || envVar === 'prod') {
            this.currentEnvironment = 'prod';
            this.config = this.getDefaultConfig('prod');
            return 'prod';
        }

        // Priority 2: Configuration file
        try {
            const configPath = path.join(process.cwd(), '.kiro', 'environment.json');
            const content = await fs.readFile(configPath, 'utf-8');
            const config = JSON.parse(content);

            if (config.environment === 'prod' || config.environment === 'production') {
                this.currentEnvironment = 'prod';
                this.config = { ...this.getDefaultConfig('prod'), ...config };
                return 'prod';
            }
        } catch (error) {
            // Config file doesn't exist or is invalid, continue with default
        }

        // Default: dev environment
        this.currentEnvironment = 'dev';
        this.config = this.getDefaultConfig('dev');
        return 'dev';
    }

    /**
     * Get default configuration for an environment
     */
    private getDefaultConfig(environment: Environment): EnvironmentConfig {
        if (environment === 'prod') {
            return {
                environment: 'prod',
                requireApprovalForInfraChanges: true,
                requireApprovalForDeployments: true,
                requireApprovalForBudgetIncreases: true,
                autonomousOperation: false,
            };
        } else {
            return {
                environment: 'dev',
                requireApprovalForInfraChanges: false,
                requireApprovalForDeployments: false,
                requireApprovalForBudgetIncreases: false,
                autonomousOperation: true,
            };
        }
    }

    /**
     * Load budget policy for current environment
     */
    async loadBudgetPolicy(policyPath?: string): Promise<BudgetPolicy> {
        const resolvedPath = policyPath || this.config.budgetPolicyPath;

        if (!resolvedPath) {
            // Use default budget policy
            return this.getDefaultBudgetPolicy(this.currentEnvironment);
        }

        try {
            const content = await fs.readFile(resolvedPath, 'utf-8');
            const policy: BudgetPolicy = JSON.parse(content);

            // Validate policy matches current environment
            if (policy.environment !== this.currentEnvironment) {
                console.warn(
                    `Budget policy environment (${policy.environment}) does not match current environment (${this.currentEnvironment})`
                );
            }

            this.budgetPolicy = policy;
            return policy;
        } catch (error) {
            console.error(`Failed to load budget policy from ${resolvedPath}:`, error);
            // Fall back to default policy
            return this.getDefaultBudgetPolicy(this.currentEnvironment);
        }
    }

    /**
     * Get default budget policy for an environment
     */
    private getDefaultBudgetPolicy(environment: Environment): BudgetPolicy {
        if (environment === 'prod') {
            return {
                id: 'default-prod-policy',
                environment: 'prod',
                limits: {
                    total: 1000,
                    currency: 'GBP',
                    duration: '72h',
                    perService: {
                        gamelift: 500,
                        cognito: 100,
                        dynamodb: 200,
                        lambda: 100,
                        other: 100,
                    },
                },
                enforcement: {
                    mode: 'block',
                    warningThreshold: 0.8,
                    approvalRequired: true,
                },
            };
        } else {
            return {
                id: 'default-dev-policy',
                environment: 'dev',
                limits: {
                    total: 100,
                    currency: 'GBP',
                    duration: '72h',
                },
                enforcement: {
                    mode: 'report',
                    warningThreshold: 0.9,
                    approvalRequired: false,
                },
            };
        }
    }

    /**
     * Get current environment
     */
    getEnvironment(): Environment {
        return this.currentEnvironment;
    }

    /**
     * Get current configuration
     */
    getConfig(): EnvironmentConfig {
        return { ...this.config };
    }

    /**
     * Get current budget policy
     */
    getBudgetPolicy(): BudgetPolicy | undefined {
        return this.budgetPolicy;
    }

    /**
     * Check if approval is required for an operation type
     */
    requiresApproval(operationType: 'infra_change' | 'deployment' | 'budget_increase'): boolean {
        switch (operationType) {
            case 'infra_change':
                return this.config.requireApprovalForInfraChanges;
            case 'deployment':
                return this.config.requireApprovalForDeployments;
            case 'budget_increase':
                return this.config.requireApprovalForBudgetIncreases;
            default:
                return false;
        }
    }

    /**
     * Check if autonomous operation is allowed
     */
    isAutonomousOperationAllowed(): boolean {
        return this.config.autonomousOperation;
    }

    /**
     * Set environment (for testing)
     */
    setEnvironment(environment: Environment): void {
        this.currentEnvironment = environment;
        this.config = this.getDefaultConfig(environment);
    }

    /**
     * Update configuration
     */
    updateConfig(updates: Partial<EnvironmentConfig>): void {
        this.config = { ...this.config, ...updates };
    }
}

// Singleton instance
let environmentManager: EnvironmentManager | null = null;

/**
 * Get the singleton EnvironmentManager instance
 */
export function getEnvironmentManager(): EnvironmentManager {
    if (!environmentManager) {
        environmentManager = new EnvironmentManager();
    }
    return environmentManager;
}

/**
 * Reset the singleton (for testing)
 */
export function resetEnvironmentManager(): void {
    environmentManager = null;
}

