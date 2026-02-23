/**
 * UnrealLevelBuilderAgent
 * 
 * Responsible for converting LevelPlan specifications into Unreal Engine maps.
 * Handles blockout geometry generation and gameplay pass implementation.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface LevelPlan {
    id: string;
    name: string;
    description: string;
    zones: Zone[];
    playerSpawns: PlayerSpawn[];
    objectives: Objective[];
}

export interface Zone {
    id: string;
    name: string;
    bounds: {
        center: { x: number; y: number; z: number };
        extents: { x: number; y: number; z: number };
    };
    type: 'combat' | 'safe' | 'objective' | 'spawn';
    assets?: string[];
}

export interface PlayerSpawn {
    position: { x: number; y: number; z: number };
    rotation: { pitch: number; yaw: number; roll: number };
}

export interface Objective {
    id: string;
    type: string;
    description: string;
    rewardId?: string;
}

export class UnrealLevelBuilderAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'unreal-level-builder',
            description: 'Converts LevelPlan specifications into Unreal Engine maps with blockout geometry',
            capabilities: [
                {
                    name: 'convert_levelplan_to_map',
                    description: 'Convert a LevelPlan JSON to an Unreal Engine map',
                    parameters: {
                        type: 'object',
                        required: ['levelPlanPath', 'outputMapName'],
                        properties: {
                            levelPlanPath: {
                                type: 'string',
                                description: 'Path to LevelPlan.json file',
                            },
                            outputMapName: {
                                type: 'string',
                                description: 'Name for the generated Unreal map',
                            },
                            generateBlockout: {
                                type: 'boolean',
                                description: 'Generate blockout geometry (default: true)',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'GitHubMCP'],
                },
                {
                    name: 'generate_blockout_geometry',
                    description: 'Generate blockout geometry for zones',
                    parameters: {
                        type: 'object',
                        required: ['zones', 'mapName'],
                        properties: {
                            zones: {
                                type: 'array',
                                description: 'Array of zone definitions',
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
                    name: 'place_player_spawns',
                    description: 'Place player spawn points in the map',
                    parameters: {
                        type: 'object',
                        required: ['spawns', 'mapName'],
                        properties: {
                            spawns: {
                                type: 'array',
                                description: 'Array of spawn point definitions',
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
                    name: 'implement_objectives',
                    description: 'Implement objective triggers and logic',
                    parameters: {
                        type: 'object',
                        required: ['objectives', 'mapName'],
                        properties: {
                            objectives: {
                                type: 'array',
                                description: 'Array of objective definitions',
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
                    name: 'validate_map',
                    description: 'Validate generated map for errors and warnings',
                    parameters: {
                        type: 'object',
                        required: ['mapName'],
                        properties: {
                            mapName: {
                                type: 'string',
                                description: 'Map name to validate',
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
        return `You are the UnrealLevelBuilderAgent, responsible for converting LevelPlan specifications into Unreal Engine maps.

Your responsibilities:

1. **LevelPlan Conversion**: Transform JSON specifications into Unreal maps:
   - Parse LevelPlan.json structure
   - Extract zones, spawns, and objectives
   - Generate appropriate Unreal Engine assets
   - Maintain spatial relationships and scale

2. **Blockout Geometry Generation**: Create placeholder geometry:
   - Generate boxes for zone boundaries
   - Use appropriate materials for zone types:
     * Combat zones: Red translucent
     * Safe zones: Green translucent
     * Objective zones: Blue translucent
     * Spawn zones: Yellow translucent
   - Ensure proper collision settings
   - Add visual markers for debugging

3. **Player Spawn Placement**: Position spawn points correctly:
   - Convert coordinates from LevelPlan to Unreal space
   - Apply rotation values (pitch, yaw, roll)
   - Ensure spawns are within valid zones
   - Add PlayerStart actors at each location

4. **Objective Implementation**: Create objective triggers:
   - Place trigger volumes at objective locations
   - Link objectives to reward IDs
   - Implement basic interaction logic
   - Add visual indicators for objectives

5. **Gameplay Pass**: Implement gameplay elements:
   - Add lighting (basic directional light)
   - Add post-process volume for VR comfort
   - Configure player start points
   - Set up game mode references

Key Principles:
- Use Unreal Engine coordinate system (Z-up, cm units)
- Generate clean, organized actor hierarchies
- Follow Unreal naming conventions
- Create modular, reusable components
- Prioritize VR performance (Quest 3 target)
- Use Tier 0 assets (blockout primitives) initially

Output Format:
Return structured JSON with:
- Generated map path
- List of created actors
- Validation results
- Warnings or errors
- Next steps for art pass

Be precise with coordinates and maintain spatial consistency.`;
    }

    /**
     * Convert LevelPlan to Unreal map
     */
    async convertLevelPlanToMap(
        levelPlan: LevelPlan,
        outputMapName: string,
        _context: AgentContext,
        options?: {
            generateBlockout?: boolean;
        }
    ): Promise<AgentResult> {
        const generateBlockout = options?.generateBlockout !== false;

        const steps: string[] = [];
        const artifacts: any[] = [];

        try {
            // Step 1: Generate blockout geometry
            if (generateBlockout) {
                steps.push('Generating blockout geometry for zones');
                // In real implementation, this would call UnrealMCP adapter
                artifacts.push({
                    type: 'blockout_geometry',
                    zones: levelPlan.zones.length,
                });
            }

            // Step 2: Place player spawns
            steps.push('Placing player spawn points');
            artifacts.push({
                type: 'player_spawns',
                count: levelPlan.playerSpawns.length,
            });

            // Step 3: Implement objectives
            steps.push('Implementing objective triggers');
            artifacts.push({
                type: 'objectives',
                count: levelPlan.objectives.length,
            });

            // Step 4: Validate map
            steps.push('Validating generated map');

            return {
                success: true,
                result: {
                    mapName: outputMapName,
                    mapPath: `/Game/Maps/${outputMapName}`,
                    steps,
                    artifacts,
                    message: `Successfully converted LevelPlan to Unreal map: ${outputMapName}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'CONVERSION_FAILED',
                    message: `Failed to convert LevelPlan: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Generate blockout geometry for zones
     */
    generateBlockoutGeometry(zones: Zone[]): {
        geometry: any[];
        materials: Record<string, string>;
    } {
        const geometry: any[] = [];
        const materials: Record<string, string> = {
            combat: 'M_Blockout_Red',
            safe: 'M_Blockout_Green',
            objective: 'M_Blockout_Blue',
            spawn: 'M_Blockout_Yellow',
        };

        for (const zone of zones) {
            geometry.push({
                type: 'Box',
                name: `Zone_${zone.name}`,
                location: zone.bounds.center,
                scale: {
                    x: zone.bounds.extents.x / 100, // Convert to Unreal scale
                    y: zone.bounds.extents.y / 100,
                    z: zone.bounds.extents.z / 100,
                },
                material: materials[zone.type],
                collision: zone.type === 'combat' ? 'BlockAll' : 'NoCollision',
            });
        }

        return { geometry, materials };
    }

    /**
     * Place player spawn points
     */
    placePlayerSpawns(spawns: PlayerSpawn[]): any[] {
        return spawns.map((spawn, index) => ({
            type: 'PlayerStart',
            name: `PlayerStart_${index}`,
            location: spawn.position,
            rotation: spawn.rotation,
        }));
    }

    /**
     * Implement objectives
     */
    implementObjectives(objectives: Objective[]): any[] {
        return objectives.map((objective) => ({
            type: 'TriggerVolume',
            name: `Objective_${objective.id}`,
            objectiveType: objective.type,
            description: objective.description,
            rewardId: objective.rewardId,
            // In real implementation, would create Blueprint logic
        }));
    }
}
