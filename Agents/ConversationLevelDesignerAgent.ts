/**
 * ConversationLevelDesignerAgent
 * 
 * Responsible for:
 * - Natural language to LevelPlan.json conversion
 * - Zone layout generation
 * - Objective placement logic
 * 
 * This agent translates high-level level descriptions into structured
 * LevelPlan specifications that can be used to generate Unreal Engine maps.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export class ConversationLevelDesignerAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'conversation-level-designer',
            description:
                'Converts natural language level descriptions into structured LevelPlan specifications',
            capabilities: [
                {
                    name: 'generate_level_plan',
                    description:
                        'Convert a natural language level description into a LevelPlan.json specification',
                    parameters: {
                        type: 'object',
                        required: ['description'],
                        properties: {
                            description: {
                                type: 'string',
                                description: 'Natural language description of the level',
                            },
                            constraints: {
                                type: 'object',
                                description: 'Constraints (player count, size limits, theme)',
                            },
                            rewardCatalog: {
                                type: 'array',
                                description: 'Available reward IDs from rewards_catalog.json',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP', 'GitHubMCP'],
                },
                {
                    name: 'design_zone_layout',
                    description:
                        'Design spatial layout of zones with proper bounds and connectivity',
                    parameters: {
                        type: 'object',
                        required: ['zoneTypes', 'playerCount'],
                        properties: {
                            zoneTypes: {
                                type: 'array',
                                description: 'Types of zones needed (combat, safe, objective, spawn)',
                            },
                            playerCount: {
                                type: 'number',
                                description: 'Expected player count (10-15)',
                            },
                            mapSize: {
                                type: 'object',
                                description: 'Overall map dimensions',
                            },
                        },
                    },
                },
                {
                    name: 'place_objectives',
                    description:
                        'Place objectives in zones with appropriate reward assignments',
                    parameters: {
                        type: 'object',
                        required: ['zones', 'objectiveCount'],
                        properties: {
                            zones: {
                                type: 'array',
                                description: 'Available zones for objective placement',
                            },
                            objectiveCount: {
                                type: 'number',
                                description: 'Number of objectives to place',
                            },
                            rewardIds: {
                                type: 'array',
                                description: 'Available reward IDs to assign',
                            },
                        },
                    },
                },
                {
                    name: 'validate_level_plan',
                    description:
                        'Validate a LevelPlan against schema and gameplay requirements',
                    parameters: {
                        type: 'object',
                        required: ['levelPlan'],
                        properties: {
                            levelPlan: {
                                type: 'object',
                                description: 'LevelPlan to validate',
                            },
                            schemaPath: {
                                type: 'string',
                                description: 'Path to LevelPlan.schema.json',
                            },
                        },
                    },
                    mcpAdapters: ['GitHubMCP'],
                },
            ],
            model: {
                provider: 'bedrock',
                modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
                region: 'eu-west-1',
                temperature: 0.7, // Higher temperature for creative level design
            },
        };

        super(config, mcpAdapters);
    }

    protected getSystemPrompt(): string {
        return `You are the ConversationLevelDesignerAgent, a specialized AI for designing VR multiplayer levels for Meta Quest 3.

Your responsibilities:

1. **Natural Language to LevelPlan Conversion**: Transform descriptions into structured specifications:
   - Parse level descriptions for key elements (theme, layout, objectives)
   - Generate zone definitions with spatial bounds
   - Place player spawn points strategically
   - Assign objectives with appropriate rewards
   - Ensure compliance with LevelPlan.schema.json

2. **Zone Layout Design**: Create spatial layouts that support gameplay:
   - Combat zones: Open areas for player engagement
   - Safe zones: Protected areas for regrouping
   - Objective zones: Areas with gameplay goals
   - Spawn zones: Player entry points
   - Ensure zones are appropriately sized for 10-15 players
   - Consider VR comfort (avoid tight spaces, provide clear sightlines)

3. **Objective Placement**: Strategic placement of gameplay objectives:
   - Distribute objectives across zones
   - Assign reward IDs from the rewards catalog
   - Balance difficulty and accessibility
   - Create interesting gameplay flow
   - Ensure objectives are reachable and visible

4. **Validation**: Ensure level plans are valid and playable:
   - Validate against LevelPlan.schema.json
   - Check for sufficient spawn points (10-15)
   - Verify zone connectivity
   - Ensure reward IDs exist in catalog
   - Check spatial bounds don't overlap inappropriately

VR Design Principles:
- Avoid motion sickness triggers (rapid movement, tight spaces)
- Provide clear navigation cues
- Design for standing/room-scale VR
- Consider Quest 3 performance limits
- Ensure accessibility for all comfort levels

Output Format:
Return valid LevelPlan.json conforming to the schema:
{
  "id": "uuid",
  "name": "Level Name",
  "description": "Level description",
  "zones": [...],
  "playerSpawns": [...],
  "objectives": [...]
}

Be creative but practical. Design levels that are fun, balanced, and technically feasible.`;
    }
}
