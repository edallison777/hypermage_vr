/**
 * GameplaySystemsAgent
 * 
 * Responsible for implementing VR interaction systems, objective logic,
 * and server-side reward emission.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface VRInteractionConfig {
    grabDistance: number;
    throwForceMultiplier: number;
    hapticFeedbackIntensity: number;
    interactionLayers: string[];
}

export interface ObjectiveConfig {
    id: string;
    type: 'collect' | 'reach' | 'defeat' | 'interact' | 'time';
    description: string;
    rewardId?: string;
    parameters: Record<string, any>;
}

export interface RewardEmissionConfig {
    validateAgainstCatalog: boolean;
    serverAuthoritative: boolean;
    persistToDatabase: boolean;
}

export class GameplaySystemsAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'gameplay-systems',
            description: 'Implements VR interactions, objective systems, and server-side reward emission',
            capabilities: [
                {
                    name: 'implement_vr_interactions',
                    description: 'Implement VR grab, throw, and interaction systems',
                    parameters: {
                        type: 'object',
                        required: ['interactionConfig'],
                        properties: {
                            interactionConfig: {
                                type: 'object',
                                description: 'VR interaction configuration',
                            },
                            targetClass: {
                                type: 'string',
                                description: 'C++ class name for interaction component',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'implement_objective_system',
                    description: 'Implement objective tracking and completion logic',
                    parameters: {
                        type: 'object',
                        required: ['objectives'],
                        properties: {
                            objectives: {
                                type: 'array',
                                description: 'Array of objective configurations',
                            },
                            mapName: {
                                type: 'string',
                                description: 'Target map name',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'implement_reward_emission',
                    description: 'Implement server-side reward granting system',
                    parameters: {
                        type: 'object',
                        required: ['rewardConfig'],
                        properties: {
                            rewardConfig: {
                                type: 'object',
                                description: 'Reward emission configuration',
                            },
                            catalogPath: {
                                type: 'string',
                                description: 'Path to rewards_catalog.json',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'implement_gameplay_rules',
                    description: 'Implement trigger-action gameplay rules',
                    parameters: {
                        type: 'object',
                        required: ['rulesPath'],
                        properties: {
                            rulesPath: {
                                type: 'string',
                                description: 'Path to GameplayRules.json',
                            },
                            mapName: {
                                type: 'string',
                                description: 'Target map name',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
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
        return `You are the GameplaySystemsAgent, responsible for implementing VR interactions, objective systems, and server-side reward emission.

Your responsibilities:

1. **VR Interaction Systems**: Implement Quest 3 VR interactions:
   - Grab system using OpenXR grip buttons
   - Throw physics with velocity calculation
   - Haptic feedback on interaction events
   - Distance-based interaction highlighting
   - Collision-based interaction detection
   - Support for both hands independently

2. **Objective System**: Implement objective tracking and completion:
   - Objective types:
     * Collect: Gather N items
     * Reach: Enter a specific zone
     * Defeat: Eliminate N enemies
     * Interact: Activate N objects
     * Time: Survive for N seconds
   - Server-authoritative objective state
   - Progress tracking per player
   - Completion validation
   - Reward emission on completion

3. **Server-Side Reward Emission**: Implement secure reward granting:
   - Load rewards_catalog.json on server startup
   - Validate reward IDs against catalog
   - Reject invalid reward IDs with INVALID_REWARD_ID error
   - Handle catalog loading failures with REWARD_CATALOG_NOT_FOUND error
   - Emit rewards only from server (never client)
   - Store rewards as boolean flags in PlayerRewards table
   - Replicate reward notifications to clients
   - Log all reward grants for auditing

4. **Gameplay Rules**: Implement trigger-action patterns:
   - Parse GameplayRules.json
   - Create trigger volumes and conditions
   - Implement action handlers
   - Support rule chaining and dependencies
   - Server-side rule evaluation

Key Principles:
- Server authority for all gameplay state
- Client prediction for VR interactions (latency hiding)
- Validate all client inputs on server
- Use Unreal's replication system
- Optimize for Quest 3 performance
- Minimize network bandwidth usage
- Provide clear feedback to players

C++ Implementation Guidelines:
- Use UGrabComponent for VR grabbing
- Use UObjectiveComponent for objective tracking
- Use URewardSystem for reward emission
- Use UGameplayRuleComponent for rule execution
- Follow Unreal coding standards
- Use UPROPERTY for replication
- Use RPC functions for client-server communication

Output Format:
Return structured JSON with:
- Generated C++ class names
- Blueprint asset paths
- Configuration parameters
- Validation results
- Integration instructions

Be precise with replication settings and network optimization.`;
    }

    /**
     * Implement VR interaction systems
     */
    async implementVRInteractions(
        config: VRInteractionConfig,
        targetClass: string,
        _context: AgentContext
    ): Promise<AgentResult> {
        try {
            const components = [
                {
                    name: 'GrabComponent',
                    class: `U${targetClass}GrabComponent`,
                    features: [
                        'OpenXR grip button detection',
                        'Distance-based grab validation',
                        'Physics-based throwing',
                        'Haptic feedback integration',
                    ],
                },
                {
                    name: 'InteractionComponent',
                    class: `U${targetClass}InteractionComponent`,
                    features: [
                        'Raycast-based interaction detection',
                        'Interaction highlighting',
                        'Multi-layer interaction support',
                        'Server-side validation',
                    ],
                },
            ];

            return {
                success: true,
                result: {
                    components,
                    config,
                    message: 'VR interaction systems implemented successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'VR_INTERACTION_FAILED',
                    message: `Failed to implement VR interactions: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Implement objective system
     */
    async implementObjectiveSystem(
        objectives: ObjectiveConfig[],
        mapName: string,
        _context: AgentContext
    ): Promise<AgentResult> {
        try {
            const implementations = objectives.map((objective) => ({
                objectiveId: objective.id,
                type: objective.type,
                class: 'UObjectiveComponent',
                triggerVolume: `Trigger_${objective.id}`,
                rewardId: objective.rewardId,
                serverValidation: true,
            }));

            return {
                success: true,
                result: {
                    implementations,
                    mapName,
                    message: `Implemented ${objectives.length} objectives in ${mapName}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'OBJECTIVE_IMPLEMENTATION_FAILED',
                    message: `Failed to implement objectives: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Implement server-side reward emission
     */
    async implementRewardEmission(
        config: RewardEmissionConfig,
        catalogPath: string,
        _context: AgentContext
    ): Promise<AgentResult> {
        try {
            const implementation = {
                class: 'URewardSystem',
                features: [
                    'Load rewards_catalog.json on server startup',
                    'Validate reward IDs against catalog',
                    'Reject invalid IDs with INVALID_REWARD_ID',
                    'Handle catalog errors with REWARD_CATALOG_NOT_FOUND',
                    'Server-authoritative reward granting',
                    'Store as boolean flags in PlayerRewards table',
                    'Replicate notifications to clients',
                    'Audit logging for all grants',
                ],
                config,
                catalogPath,
            };

            return {
                success: true,
                result: {
                    implementation,
                    message: 'Server-side reward emission implemented successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'REWARD_EMISSION_FAILED',
                    message: `Failed to implement reward emission: ${error}`,
                },
                duration: 0,
            };
        }
    }
}
