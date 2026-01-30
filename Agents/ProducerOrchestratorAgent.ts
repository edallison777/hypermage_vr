/**
 * ProducerOrchestratorAgent
 * 
 * Responsible for:
 * - Task decomposition and milestone gating
 * - Reward catalog enforcement
 * - Definitions of done validation
 * 
 * This agent acts as a high-level coordinator that breaks down complex
 * specifications into manageable tasks and ensures quality gates are met.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export class ProducerOrchestratorAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'producer-orchestrator',
            description:
                'High-level coordinator for task decomposition, milestone gating, and quality validation',
            capabilities: [
                {
                    name: 'decompose_specification',
                    description:
                        'Break down a natural language specification into structured tasks with dependencies',
                    parameters: {
                        type: 'object',
                        required: ['specification'],
                        properties: {
                            specification: {
                                type: 'string',
                                description: 'Natural language specification to decompose',
                            },
                            context: {
                                type: 'object',
                                description: 'Additional context (existing levels, budget, environment)',
                            },
                        },
                    },
                },
                {
                    name: 'validate_milestone',
                    description:
                        'Validate that a milestone has been completed according to its definition of done',
                    parameters: {
                        type: 'object',
                        required: ['milestoneId', 'artifacts'],
                        properties: {
                            milestoneId: {
                                type: 'string',
                                description: 'ID of the milestone to validate',
                            },
                            artifacts: {
                                type: 'array',
                                description: 'Artifacts produced during milestone execution',
                            },
                            definitionOfDone: {
                                type: 'array',
                                description: 'Criteria that must be met for completion',
                            },
                        },
                    },
                },
                {
                    name: 'enforce_reward_catalog',
                    description:
                        'Validate that all reward IDs in a specification exist in the rewards catalog',
                    parameters: {
                        type: 'object',
                        required: ['rewardIds', 'catalogPath'],
                        properties: {
                            rewardIds: {
                                type: 'array',
                                description: 'List of reward IDs to validate',
                            },
                            catalogPath: {
                                type: 'string',
                                description: 'Path to rewards_catalog.json',
                            },
                        },
                    },
                    mcpAdapters: ['GitHubMCP'],
                },
                {
                    name: 'create_execution_plan',
                    description:
                        'Create a detailed execution plan with agent assignments and dependencies',
                    parameters: {
                        type: 'object',
                        required: ['tasks'],
                        properties: {
                            tasks: {
                                type: 'array',
                                description: 'List of tasks to plan',
                            },
                            availableAgents: {
                                type: 'array',
                                description: 'List of available agents and their capabilities',
                            },
                        },
                    },
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
                region: 'eu-west-1',
                temperature: 0.3, // Lower temperature for more consistent planning
            },
        };

        super(config, mcpAdapters);
    }

    protected getSystemPrompt(): string {
        return `You are the ProducerOrchestratorAgent, a high-level coordinator responsible for breaking down complex VR multiplayer system specifications into manageable tasks.

Your responsibilities:

1. **Task Decomposition**: Break down natural language specifications into structured tasks with:
   - Clear task descriptions
   - Dependencies between tasks
   - Agent assignments based on capabilities
   - Estimated duration and cost
   - Definitions of done

2. **Milestone Gating**: Ensure quality gates are met before proceeding:
   - Validate artifacts against definitions of done
   - Check that all required outputs are present
   - Verify quality criteria are satisfied
   - Block progression if criteria not met

3. **Reward Catalog Enforcement**: Ensure all reward IDs are valid:
   - Check reward IDs against the rewards catalog
   - Reject invalid reward IDs
   - Suggest valid alternatives if needed

4. **Execution Planning**: Create detailed execution plans:
   - Assign tasks to appropriate agents
   - Determine execution order based on dependencies
   - Calculate cost estimates
   - Identify potential risks

Key Principles:
- Break work into vertical slices when possible
- Prioritize end-to-end validation over feature breadth
- Enforce strict quality gates at milestones
- Ensure all specifications are testable
- Track costs and enforce budget limits

Output Format:
Always return structured JSON that can be parsed by the orchestrator. Include:
- Task list with IDs, descriptions, dependencies
- Agent assignments
- Cost estimates
- Risk assessments
- Validation criteria

Be precise, thorough, and enforce quality standards rigorously.`;
    }
}
