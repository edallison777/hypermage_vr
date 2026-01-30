/**
 * Plan Generator Service
 * 
 * Analyzes natural language specifications and generates execution plans
 */

import { v4 as uuidv4 } from 'uuid';
import { ExecutionPlan, PlanStep, PlanContext } from '../types';
import { logger } from '../utils/logger';

export class PlanGenerator {
    /**
     * Generate execution plan from natural language specification
     */
    public async generatePlan(
        specification: string,
        context: PlanContext
    ): Promise<ExecutionPlan> {
        logger.info('Generating plan', { specification, context });

        const planId = uuidv4();
        const steps = this.analyzeSpecification(specification, context);
        const estimatedCost = this.calculateTotalCost(steps);
        const estimatedDuration = this.calculateTotalDuration(steps);

        const plan: ExecutionPlan = {
            id: planId,
            createdAt: new Date().toISOString(),
            specification,
            context,
            steps,
            estimatedCost,
            estimatedDuration,
            status: 'pending',
        };

        logger.info('Plan generated', {
            planId,
            stepCount: steps.length,
            estimatedCost,
            estimatedDuration,
        });

        return plan;
    }

    /**
     * Analyze specification and determine required steps
     */
    private analyzeSpecification(specification: string, context: PlanContext): PlanStep[] {
        const steps: PlanStep[] = [];
        const spec = specification.toLowerCase();

        // Detect if this is a level creation request
        if (this.isLevelCreationRequest(spec)) {
            steps.push(...this.generateLevelCreationSteps(specification, context));
        }

        // Detect if this is a deployment request
        if (this.isDeploymentRequest(spec)) {
            steps.push(...this.generateDeploymentSteps(context));
        }

        // Detect if this is an asset generation request
        if (this.isAssetGenerationRequest(spec)) {
            steps.push(...this.generateAssetGenerationSteps(specification));
        }

        // If no specific pattern detected, create a generic plan
        if (steps.length === 0) {
            steps.push(...this.generateGenericPlan(specification, context));
        }

        return steps;
    }

    private isLevelCreationRequest(spec: string): boolean {
        const keywords = ['level', 'map', 'arena', 'environment', 'world', 'scene'];
        return keywords.some((keyword) => spec.includes(keyword));
    }

    private isDeploymentRequest(spec: string): boolean {
        const keywords = ['deploy', 'publish', 'release', 'infrastructure'];
        return keywords.some((keyword) => spec.includes(keyword));
    }

    private isAssetGenerationRequest(spec: string): boolean {
        const keywords = ['asset', 'model', 'texture', 'material', 'mesh'];
        return keywords.some((keyword) => spec.includes(keyword));
    }

    private generateLevelCreationSteps(
        specification: string,
        _context: PlanContext
    ): PlanStep[] {
        return [
            {
                id: uuidv4(),
                name: 'Parse Level Specification',
                description: 'Convert natural language to LevelPlan.json',
                agent: 'ConversationLevelDesignerAgent',
                capability: 'parse_specification',
                parameters: { specification },
                dependencies: [],
                estimatedDuration: 30000,
                estimatedCost: 0,
                optional: false,
            },
            {
                id: uuidv4(),
                name: 'Generate Level Geometry',
                description: 'Create blockout geometry in Unreal Engine',
                agent: 'UnrealLevelBuilderAgent',
                capability: 'generate_level',
                parameters: { tier: 0 },
                dependencies: [],
                estimatedDuration: 120000,
                estimatedCost: 0,
                optional: false,
            },
            {
                id: uuidv4(),
                name: 'Implement Gameplay Systems',
                description: 'Add objectives, spawn points, and game rules',
                agent: 'GameplaySystemsAgent',
                capability: 'implement_gameplay',
                parameters: {},
                dependencies: [],
                estimatedDuration: 60000,
                estimatedCost: 0,
                optional: false,
            },
        ];
    }

    private generateDeploymentSteps(_context: PlanContext): PlanStep[] {
        return [
            {
                id: uuidv4(),
                name: 'Build Unreal Project',
                description: 'Build dedicated server for Quest 3',
                agent: 'UnrealBuilderAgent',
                capability: 'build_project',
                parameters: { configuration: 'Shipping', platform: 'Android' },
                dependencies: [],
                estimatedDuration: 300000,
                estimatedCost: 0,
                optional: false,
            },
            {
                id: uuidv4(),
                name: 'Deploy GameLift Fleet',
                description: 'Deploy dedicated server fleet to AWS',
                agent: 'DevOpsAWSAgent',
                capability: 'deploy_gamelift',
                parameters: { region: 'eu-west-1', maxShards: 3 },
                dependencies: [],
                estimatedDuration: 180000,
                estimatedCost: 18.36,
                optional: false,
            },
            {
                id: uuidv4(),
                name: 'Configure Matchmaking',
                description: 'Set up FlexMatch configuration',
                agent: 'DevOpsAWSAgent',
                capability: 'configure_matchmaking',
                parameters: { minPlayers: 10, maxPlayers: 15 },
                dependencies: [],
                estimatedDuration: 60000,
                estimatedCost: 0,
                optional: false,
            },
        ];
    }

    private generateAssetGenerationSteps(specification: string): PlanStep[] {
        return [
            {
                id: uuidv4(),
                name: 'Generate Placeholder Assets',
                description: 'Create Tier 1 placeholder assets from concept art',
                agent: 'TechArtVFXAudioAgent',
                capability: 'generate_placeholder',
                parameters: { specification },
                dependencies: [],
                estimatedDuration: 90000,
                estimatedCost: 5.0,
                optional: false,
            },
            {
                id: uuidv4(),
                name: 'Import Assets to Unreal',
                description: 'Import generated assets into Unreal project',
                agent: 'AssetPipelineAgent',
                capability: 'import_assets',
                parameters: {},
                dependencies: [],
                estimatedDuration: 30000,
                estimatedCost: 0,
                optional: false,
            },
        ];
    }

    private generateGenericPlan(specification: string, _context: PlanContext): PlanStep[] {
        return [
            {
                id: uuidv4(),
                name: 'Analyze Request',
                description: 'Analyze specification and determine required actions',
                agent: 'ProducerOrchestratorAgent',
                capability: 'analyze_specification',
                parameters: { specification },
                dependencies: [],
                estimatedDuration: 15000,
                estimatedCost: 0,
                optional: false,
            },
        ];
    }

    private calculateTotalCost(steps: PlanStep[]): number {
        return steps.reduce((total, step) => total + step.estimatedCost, 0);
    }

    private calculateTotalDuration(steps: PlanStep[]): number {
        // Simple sum for now; in reality would need to account for parallelization
        return steps.reduce((total, step) => total + step.estimatedDuration, 0);
    }
}
