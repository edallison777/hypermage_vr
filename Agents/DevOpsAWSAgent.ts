/**
 * DevOpsAWSAgent
 * 
 * Responsible for Terraform orchestration, CI/CD pipeline management,
 * and observability setup for AWS infrastructure.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface TerraformConfig {
    action: 'plan' | 'apply' | 'destroy';
    environment: 'dev' | 'staging' | 'prod';
    modules: string[];
    autoApprove: boolean;
}

export interface CICDConfig {
    pipeline: 'validate' | 'build' | 'test' | 'deploy';
    trigger: 'push' | 'pr' | 'manual' | 'schedule';
    environment: 'dev' | 'staging' | 'prod';
}

export interface ObservabilityConfig {
    metrics: boolean;
    logs: boolean;
    traces: boolean;
    alerts: boolean;
    dashboards: boolean;
}

export class DevOpsAWSAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'devops-aws',
            description: 'Manages Terraform, CI/CD pipelines, and observability',
            capabilities: [
                {
                    name: 'execute_terraform',
                    description: 'Execute Terraform plan, apply, or destroy',
                    parameters: {
                        type: 'object',
                        required: ['terraformConfig'],
                        properties: {
                            terraformConfig: {
                                type: 'object',
                                description: 'Terraform configuration',
                            },
                        },
                    },
                    mcpAdapters: ['AWSMCP', 'LocalProcessMCP'],
                },
                {
                    name: 'manage_cicd_pipeline',
                    description: 'Create or update CI/CD pipeline',
                    parameters: {
                        type: 'object',
                        required: ['cicdConfig'],
                        properties: {
                            cicdConfig: {
                                type: 'object',
                                description: 'CI/CD configuration',
                            },
                        },
                    },
                    mcpAdapters: ['GitHubMCP'],
                },
                {
                    name: 'setup_observability',
                    description: 'Set up monitoring, logging, and alerting',
                    parameters: {
                        type: 'object',
                        required: ['observabilityConfig'],
                        properties: {
                            observabilityConfig: {
                                type: 'object',
                                description: 'Observability configuration',
                            },
                        },
                    },
                    mcpAdapters: ['AWSMCP'],
                },
                {
                    name: 'deploy_infrastructure',
                    description: 'Deploy complete infrastructure stack',
                    parameters: {
                        type: 'object',
                        required: ['environment'],
                        properties: {
                            environment: {
                                type: 'string',
                                description: 'Target environment',
                            },
                            modules: {
                                type: 'array',
                                description: 'Terraform modules to deploy',
                            },
                        },
                    },
                    mcpAdapters: ['AWSMCP', 'LocalProcessMCP'],
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
                region: 'eu-west-1',
                temperature: 0.3,
            },
        };

        super(config, mcpAdapters);
    }

    protected getSystemPrompt(): string {
        return `You are the DevOpsAWSAgent, responsible for infrastructure deployment, CI/CD, and observability.

Your responsibilities:

1. **Terraform Orchestration**: Manage infrastructure as code:
   - Terraform workflow:
     * Init: Initialize Terraform working directory
     * Plan: Generate execution plan
     * Apply: Apply infrastructure changes
     * Destroy: Tear down infrastructure
   - Terraform modules:
     * /Infra/modules/gamelift-fleet
     * /Infra/modules/flexmatch
     * /Infra/modules/cognito
     * /Infra/modules/session-api
     * /Infra/modules/dynamodb
     * /Infra/modules/unreal-build
   - Environment management:
     * Dev: Auto-approve, reduced capacity
     * Staging: Manual approval, moderate capacity
     * Prod: Strict approval, full capacity
   - State management:
     * Remote state in S3
     * State locking with DynamoDB
     * Separate state per environment

2. **CI/CD Pipeline Management**: Automate build and deployment:
   - GitHub Actions workflows:
     * validate_specs: Schema validation, linting, type checking
     * build_unreal: Build server and client artifacts
     * terraform_plan: Generate infrastructure plan
     * terraform_apply_dev: Deploy to dev environment
     * release_prod: Deploy to production
   - Pipeline stages:
     * Validate: Run tests and checks
     * Build: Compile and package artifacts
     * Test: Run integration tests
     * Deploy: Apply infrastructure changes
     * Verify: Smoke tests and health checks
   - Approval gates:
     * Dev: No approval required
     * Staging: Team lead approval
     * Prod: Multiple approvals required

3. **Observability Setup**: Implement monitoring and alerting:
   - Metrics (CloudWatch):
     * Player count per shard
     * Connection success/failure rate
     * Average latency per region
     * Cost per player-hour
     * Agent execution time
     * Error rate by category
   - Logs (CloudWatch Logs):
     * Structured JSON logs
     * Log levels: DEBUG, INFO, WARN, ERROR, CRITICAL
     * Correlation IDs for tracing
     * Retention: 30 days dev, 90 days prod
   - Traces (X-Ray):
     * Request tracing across services
     * Performance bottleneck identification
     * Dependency mapping
   - Alerts (CloudWatch Alarms):
     * Budget threshold exceeded (80%, 90%, 100%)
     * High error rate (>5% over 5 minutes)
     * High latency (>200ms average over 5 minutes)
     * Authentication failures (>10 per minute)
     * Infrastructure failures
   - Dashboards (CloudWatch Dashboards):
     * Real-time player count and shard status
     * Cost tracking vs budget
     * Error rate and latency trends
     * Agent execution metrics
     * Infrastructure health

4. **Infrastructure Deployment**: Deploy complete stacks:
   - Deployment order:
     1. Networking (VPC, subnets, security groups)
     2. Cognito (user pools, app clients)
     3. DynamoDB (tables with TTL)
     4. GameLift (fleet, matchmaking)
     5. Session API (Lambda, API Gateway)
     6. Observability (CloudWatch, X-Ray)
   - Deployment validation:
     * Health checks for all services
     * Smoke tests for critical paths
     * Cost validation against budget
     * Security validation (IAM, encryption)
   - Rollback procedures:
     * Automatic rollback on health check failure
     * Manual rollback capability
     * State backup before changes

Key Principles:
- Infrastructure as code (no manual changes)
- Immutable infrastructure (replace, don't modify)
- Environment parity (dev/staging/prod similar)
- Automated testing and validation
- Cost awareness (track all changes)
- Security by default (least privilege)
- Observability from day one

Terraform Best Practices:
- Use modules for reusability
- Use variables for configuration
- Use outputs for cross-module references
- Use remote state for collaboration
- Use workspaces for environments
- Use data sources for existing resources
- Document all modules with README.md

CI/CD Best Practices:
- Fast feedback (fail fast)
- Automated testing (no manual tests)
- Deployment automation (no manual deploys)
- Approval gates for production
- Rollback capability
- Audit logging

Observability Best Practices:
- Structured logging (JSON format)
- Correlation IDs (trace requests)
- Meaningful metrics (actionable)
- Proactive alerts (prevent issues)
- Useful dashboards (at-a-glance status)

Output Format:
Return structured JSON with:
- Terraform execution results
- CI/CD pipeline status
- Observability configuration
- Deployment validation results
- Cost estimates
- Recommendations

Be precise with infrastructure specifications and cost estimates.`;
    }

    /**
     * Execute Terraform
     */
    async executeTerraform(
        config: TerraformConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const execution = {
                action: config.action,
                environment: config.environment,
                modules: config.modules,
                autoApprove: config.autoApprove,
                steps: this.getTerraformSteps(config.action),
                estimatedDuration: this.estimateTerraformDuration(config),
                requiresApproval: !config.autoApprove && config.environment === 'prod',
            };

            return {
                success: true,
                result: {
                    execution,
                    message: `Terraform ${config.action} configured for ${config.environment}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'TERRAFORM_EXECUTION_FAILED',
                    message: `Failed to execute Terraform: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Manage CI/CD pipeline
     */
    async manageCICDPipeline(
        config: CICDConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const pipeline = {
                name: config.pipeline,
                trigger: config.trigger,
                environment: config.environment,
                stages: this.getPipelineStages(config.pipeline),
                approvalRequired: config.environment === 'prod',
            };

            return {
                success: true,
                result: {
                    pipeline,
                    message: `CI/CD pipeline ${config.pipeline} configured`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'CICD_MANAGEMENT_FAILED',
                    message: `Failed to manage CI/CD pipeline: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Set up observability
     */
    async setupObservability(
        config: ObservabilityConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const observability = {
                metrics: config.metrics ? this.getMetricsConfig() : null,
                logs: config.logs ? this.getLogsConfig() : null,
                traces: config.traces ? this.getTracesConfig() : null,
                alerts: config.alerts ? this.getAlertsConfig() : null,
                dashboards: config.dashboards ? this.getDashboardsConfig() : null,
            };

            return {
                success: true,
                result: {
                    observability,
                    message: 'Observability configured successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'OBSERVABILITY_SETUP_FAILED',
                    message: `Failed to set up observability: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Deploy infrastructure
     */
    async deployInfrastructure(
        environment: string,
        modules: string[],
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const deployment = {
                environment,
                modules,
                deploymentOrder: this.getDeploymentOrder(modules),
                validation: [
                    'Health checks',
                    'Smoke tests',
                    'Cost validation',
                    'Security validation',
                ],
                estimatedCost: this.estimateDeploymentCost(environment, modules),
            };

            return {
                success: true,
                result: {
                    deployment,
                    message: `Infrastructure deployment configured for ${environment}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'DEPLOYMENT_FAILED',
                    message: `Failed to deploy infrastructure: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Get Terraform steps for action
     */
    private getTerraformSteps(action: string): string[] {
        const commonSteps = ['terraform init', 'terraform validate'];

        const actionSteps: Record<string, string[]> = {
            plan: [...commonSteps, 'terraform plan'],
            apply: [...commonSteps, 'terraform plan', 'terraform apply'],
            destroy: [...commonSteps, 'terraform plan -destroy', 'terraform destroy'],
        };

        return actionSteps[action] || commonSteps;
    }

    /**
     * Estimate Terraform duration
     */
    private estimateTerraformDuration(config: TerraformConfig): string {
        const durations: Record<string, number> = {
            plan: 2,
            apply: 10,
            destroy: 5,
        };
        const minutes = durations[config.action] || 5;
        return `${minutes} minutes`;
    }

    /**
     * Get pipeline stages
     */
    private getPipelineStages(pipeline: string): string[] {
        const stages: Record<string, string[]> = {
            validate: ['Checkout', 'Install dependencies', 'Run linting', 'Run type checking', 'Validate schemas'],
            build: ['Checkout', 'Install dependencies', 'Build artifacts', 'Upload to S3'],
            test: ['Checkout', 'Install dependencies', 'Run unit tests', 'Run integration tests', 'Generate coverage'],
            deploy: ['Checkout', 'Terraform plan', 'Approval gate', 'Terraform apply', 'Health checks'],
        };
        return stages[pipeline] || ['Checkout'];
    }

    /**
     * Get metrics configuration
     */
    private getMetricsConfig(): object {
        return {
            namespace: 'UnrealVRMultiplayer',
            metrics: [
                'PlayerCount',
                'ConnectionSuccessRate',
                'AverageLatency',
                'CostPerPlayerHour',
                'ErrorRate',
            ],
        };
    }

    /**
     * Get logs configuration
     */
    private getLogsConfig(): object {
        return {
            logGroup: '/aws/unreal-vr-multiplayer',
            retentionDays: 30,
            format: 'JSON',
        };
    }

    /**
     * Get traces configuration
     */
    private getTracesConfig(): object {
        return {
            service: 'X-Ray',
            samplingRate: 0.1,
        };
    }

    /**
     * Get alerts configuration
     */
    private getAlertsConfig(): object {
        return {
            alerts: [
                { name: 'BudgetExceeded', threshold: '100%' },
                { name: 'HighErrorRate', threshold: '5%' },
                { name: 'HighLatency', threshold: '200ms' },
            ],
        };
    }

    /**
     * Get dashboards configuration
     */
    private getDashboardsConfig(): object {
        return {
            dashboards: [
                'Player Metrics',
                'Cost Tracking',
                'Error Rates',
                'Infrastructure Health',
            ],
        };
    }

    /**
     * Get deployment order
     */
    private getDeploymentOrder(modules: string[]): string[] {
        const order = [
            'cognito',
            'dynamodb',
            'gamelift-fleet',
            'flexmatch',
            'session-api',
            'unreal-build',
        ];
        return order.filter((m) => modules.includes(m));
    }

    /**
     * Estimate deployment cost
     */
    private estimateDeploymentCost(environment: string, modules: string[]): string {
        const costs: Record<string, number> = {
            dev: 10,
            staging: 50,
            prod: 200,
        };
        const baseCost = costs[environment] || 10;
        const moduleCost = modules.length * 5;
        return `£${baseCost + moduleCost}`;
    }
}
