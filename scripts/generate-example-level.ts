/**
 * Generate Example Level from LevelPlan.example.json
 * 
 * This script demonstrates the complete workflow:
 * 1. Load LevelPlan.example.json
 * 2. Generate Unreal map with blockout geometry
 * 3. Place player spawns
 * 4. Implement objectives with reward triggers
 */

import * as fs from 'fs';
import * as path from 'path';
import { UnrealLevelBuilderAgent } from '../Agents/UnrealLevelBuilderAgent.js';
import type { LevelPlan } from '../Agents/UnrealLevelBuilderAgent.js';
import type { AgentContext } from '../Agents/types.js';

async function generateExampleLevel() {
    console.log('🎮 Generating Example Level: Crystal Cavern\n');

    // Step 1: Load LevelPlan
    console.log('📋 Step 1: Loading LevelPlan.example.json...');
    const levelPlanPath = path.join(process.cwd(), 'Specs/examples/LevelPlan.example.json');
    const levelPlanData = fs.readFileSync(levelPlanPath, 'utf8');
    const levelPlan: LevelPlan = JSON.parse(levelPlanData);

    console.log(`   ✅ Loaded: ${levelPlan.name}`);
    console.log(`   - Zones: ${levelPlan.zones.length}`);
    console.log(`   - Player Spawns: ${levelPlan.playerSpawns.length}`);
    console.log(`   - Objectives: ${levelPlan.objectives.length}\n`);

    // Step 2: Initialize UnrealLevelBuilderAgent
    console.log('🏗️  Step 2: Initializing UnrealLevelBuilderAgent...');
    const levelBuilder = new UnrealLevelBuilderAgent([]);
    console.log('   ✅ Agent initialized\n');

    // Step 3: Generate Unreal map
    console.log('🗺️  Step 3: Generating Unreal Engine map...');
    const context: AgentContext = {
        executionId: 'example-level-generation',
        planId: 'example-plan',
        stepId: 'generate-map',
        environment: 'dev',
    };

    const result = await levelBuilder.convertLevelPlanToMap(
        levelPlan,
        'CrystalCavern',
        context,
        { generateBlockout: true }
    );

    if (!result.success) {
        console.error('   ❌ Failed to generate map:', result.error);
        process.exit(1);
    }

    console.log('   ✅ Map generated successfully');
    console.log(`   - Map Name: ${result.result.mapName}`);
    console.log(`   - Map Path: ${result.result.mapPath}`);
    console.log(`   - Steps Completed: ${result.result.steps.length}\n`);

    // Step 4: Display generated artifacts
    console.log('📦 Step 4: Generated Artifacts:');
    result.result.artifacts.forEach((artifact: any, index: number) => {
        console.log(`   ${index + 1}. ${artifact.type}`);
        if (artifact.zones) console.log(`      - Zones: ${artifact.zones}`);
        if (artifact.count) console.log(`      - Count: ${artifact.count}`);
    });
    console.log();

    // Step 5: Generate blockout geometry details
    console.log('🎨 Step 5: Blockout Geometry Details:');
    const geometry = levelBuilder.generateBlockoutGeometry(levelPlan.zones);
    console.log(`   - Geometry pieces: ${geometry.geometry.length}`);
    console.log('   - Materials:');
    Object.entries(geometry.materials).forEach(([type, material]) => {
        console.log(`     * ${type}: ${material}`);
    });
    console.log();

    // Step 6: Player spawn details
    console.log('🎯 Step 6: Player Spawn Points:');
    const spawns = levelBuilder.placePlayerSpawns(levelPlan.playerSpawns);
    spawns.forEach((spawn, index) => {
        console.log(`   ${index + 1}. ${spawn.name}`);
        console.log(`      Position: (${spawn.location.x}, ${spawn.location.y}, ${spawn.location.z})`);
        console.log(`      Rotation: Yaw ${spawn.rotation.yaw}°`);
    });
    console.log();

    // Step 7: Objective implementation
    console.log('🏆 Step 7: Objectives:');
    const objectives = levelBuilder.implementObjectives(levelPlan.objectives);
    objectives.forEach((objective, index) => {
        console.log(`   ${index + 1}. ${objective.name}`);
        console.log(`      Type: ${objective.objectiveType}`);
        console.log(`      Description: ${objective.description}`);
        if (objective.rewardId) {
            console.log(`      Reward: ${objective.rewardId}`);
        }
    });
    console.log();

    // Step 8: Generate summary report
    console.log('📊 Step 8: Generating Summary Report...');
    const report = {
        levelName: levelPlan.name,
        mapPath: result.result.mapPath,
        generatedAt: new Date().toISOString(),
        statistics: {
            zones: levelPlan.zones.length,
            playerSpawns: levelPlan.playerSpawns.length,
            objectives: levelPlan.objectives.length,
            geometryPieces: geometry.geometry.length,
        },
        zoneBreakdown: {
            combat: levelPlan.zones.filter(z => z.type === 'combat').length,
            safe: levelPlan.zones.filter(z => z.type === 'safe').length,
            objective: levelPlan.zones.filter(z => z.type === 'objective').length,
            spawn: levelPlan.zones.filter(z => z.type === 'spawn').length,
        },
        rewards: levelPlan.objectives
            .filter(o => o.rewardId)
            .map(o => o.rewardId),
    };

    const reportPath = path.join(process.cwd(), 'Specs/examples/CrystalCavern-report.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.log(`   ✅ Report saved to: ${reportPath}\n`);

    // Step 9: Next steps
    console.log('🚀 Next Steps:');
    console.log('   1. Review the generated map in Unreal Editor');
    console.log('   2. Replace Tier 0 blockout assets with Tier 1 placeholders');
    console.log('   3. Test VR comfort settings (locomotion, snap turn, vignette)');
    console.log('   4. Deploy to GameLift for multiplayer testing');
    console.log('   5. Run vertical slice integration test\n');

    console.log('✨ Example level generation complete!\n');
}

// Run the script
generateExampleLevel().catch((error) => {
    console.error('❌ Error generating example level:', error);
    process.exit(1);
});
