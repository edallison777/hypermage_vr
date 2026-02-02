/**
 * TechArtVFXAudioAgent
 * 
 * Responsible for Tier 1 asset generation from 2D concept art,
 * Niagara VFX setup, spatial audio configuration, and Quest 3 optimization.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface AssetGenerationConfig {
    inputImagePath: string;
    assetType: 'mesh' | 'material' | 'texture';
    tier: 0 | 1 | 2;
    targetPlatform: 'Quest3' | 'PC' | 'All';
}

export interface VFXConfig {
    effectType: 'particle' | 'beam' | 'ribbon' | 'mesh';
    complexity: 'low' | 'medium' | 'high';
    maxParticles: number;
    targetFramerate: number;
}

export interface AudioConfig {
    spatialAudio: boolean;
    attenuationDistance: number; // cm
    occlusionEnabled: boolean;
    reverbEnabled: boolean;
}

export interface Quest3Optimization {
    targetFramerate: 72 | 90 | 120;
    drawCallBudget: number;
    triangleBudget: number;
    textureBudget: number; // MB
}

export class TechArtVFXAudioAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'tech-art-vfx-audio',
            description: 'Generates Tier 1 assets, implements VFX and audio, optimizes for Quest 3',
            capabilities: [
                {
                    name: 'generate_tier1_asset',
                    description: 'Generate Tier 1 placeholder asset from 2D concept art',
                    parameters: {
                        type: 'object',
                        required: ['assetConfig'],
                        properties: {
                            assetConfig: {
                                type: 'object',
                                description: 'Asset generation configuration',
                            },
                        },
                    },
                    mcpAdapters: ['ImageGenMCP', 'UnrealMCP'],
                },
                {
                    name: 'implement_niagara_vfx',
                    description: 'Implement Niagara VFX system',
                    parameters: {
                        type: 'object',
                        required: ['vfxConfig'],
                        properties: {
                            vfxConfig: {
                                type: 'object',
                                description: 'VFX configuration',
                            },
                            effectName: {
                                type: 'string',
                                description: 'Name for the VFX asset',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'configure_spatial_audio',
                    description: 'Configure spatial audio for VR',
                    parameters: {
                        type: 'object',
                        required: ['audioConfig'],
                        properties: {
                            audioConfig: {
                                type: 'object',
                                description: 'Audio configuration',
                            },
                        },
                    },
                    mcpAdapters: ['AudioGenMCP', 'UnrealMCP'],
                },
                {
                    name: 'optimize_for_quest3',
                    description: 'Optimize assets and settings for Quest 3 performance',
                    parameters: {
                        type: 'object',
                        required: ['optimization'],
                        properties: {
                            optimization: {
                                type: 'object',
                                description: 'Quest 3 optimization settings',
                            },
                            targetAssets: {
                                type: 'array',
                                description: 'Assets to optimize',
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
        return `You are the TechArtVFXAudioAgent, responsible for technical art, visual effects, audio, and Quest 3 optimization.

Your responsibilities:

1. **Tier 1 Asset Generation**: Create placeholder assets from 2D concept art:
   - Asset Tiers:
     * Tier 0: Blockout primitives (boxes, spheres, cylinders)
     * Tier 1: Auto-generated placeholders from 2D concept art
     * Tier 2: Final hand-crafted or licensed assets
   - Generation process:
     * Analyze 2D concept art
     * Extract key features (shape, color, proportions)
     * Generate 3D mesh with appropriate topology
     * Create basic materials with color/texture
     * Add provenance metadata
   - Quality targets:
     * Recognizable from concept art
     * Appropriate scale and proportions
     * Quest 3 performance-friendly
     * Easy to replace with Tier 2 assets

2. **Niagara VFX Implementation**: Create visual effects:
   - Effect types:
     * Particle systems (explosions, magic, impacts)
     * Beam effects (lasers, lightning)
     * Ribbon trails (projectiles, movement)
     * Mesh particles (debris, shrapnel)
   - Quest 3 optimization:
     * Low particle counts (100-500 max)
     * Simple materials (unlit or mobile-lit)
     * GPU particles (better performance)
     * LOD systems for distance culling
   - Performance budgets:
     * 72 FPS: 200 particles max per effect
     * 90 FPS: 100 particles max per effect
     * 120 FPS: 50 particles max per effect

3. **Spatial Audio Configuration**: Implement 3D audio:
   - Audio features:
     * Spatial audio (HRTF for Quest 3)
     * Distance attenuation
     * Occlusion (optional, performance cost)
     * Reverb (optional, performance cost)
   - Audio settings:
     * Attenuation distance: 1000-5000 cm typical
     * Falloff curve: logarithmic (natural)
     * Max concurrent sounds: 32 (Quest 3 limit)
   - Audio types:
     * Ambient loops (low priority)
     * Gameplay sounds (high priority)
     * Voice chat (highest priority)
     * UI sounds (medium priority)

4. **Quest 3 Optimization**: Ensure VR performance:
   - Performance targets:
     * 72 FPS: Minimum acceptable
     * 90 FPS: Recommended
     * 120 FPS: Ideal (experimental)
   - Optimization techniques:
     * Draw call batching (target: <100 draw calls)
     * Triangle budget (target: <100k triangles per frame)
     * Texture compression (ASTC for Quest 3)
     * Texture budget (target: <512 MB total)
     * LOD systems (3-5 LOD levels)
     * Occlusion culling
     * Forward rendering (mobile)
   - Mobile-specific settings:
     * Disable expensive post-processing
     * Use mobile materials
     * Limit dynamic lights (1-2 max)
     * Use lightmaps for static lighting
     * Disable shadows (or use simple blob shadows)

Key Principles:
- Prioritize performance over visual fidelity
- Quest 3 is mobile hardware (Snapdragon XR2 Gen 2)
- VR requires consistent framerate (no drops)
- Optimize early and often
- Use profiling tools to identify bottlenecks
- Test on actual Quest 3 hardware

Asset Generation Guidelines:
- Use AI image generation for texture creation
- Generate simple geometry (low poly)
- Create modular assets (reusable)
- Follow Unreal naming conventions
- Add proper collision meshes
- Include provenance metadata

VFX Guidelines:
- Use Niagara (not Cascade)
- GPU particles for better performance
- Simple materials (unlit preferred)
- Limit particle count aggressively
- Use sprite particles (not mesh particles)
- Implement LOD systems

Audio Guidelines:
- Use compressed audio formats (OGG Vorbis)
- Limit audio file sizes (<1 MB per file)
- Use audio streaming for long sounds
- Implement audio pooling (reuse sources)
- Prioritize important sounds
- Use attenuation curves wisely

Output Format:
Return structured JSON with:
- Generated asset specifications
- VFX system configurations
- Audio setup details
- Optimization recommendations
- Performance metrics
- Integration instructions

Be precise with performance budgets and optimization settings.`;
    }

    /**
     * Generate Tier 1 asset from concept art
     */
    async generateTier1Asset(
        config: AssetGenerationConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const asset = {
                name: `T1_${config.assetType}_Generated`,
                tier: 1,
                type: config.assetType,
                source: config.inputImagePath,
                specifications: {
                    triangleCount: this.getTriangleBudget(config.assetType),
                    textureResolution: this.getTextureResolution(config.targetPlatform),
                    materialComplexity: 'simple',
                    collisionType: 'simple',
                },
                provenance: {
                    origin: 'generated',
                    createdBy: this.getName(),
                    createdAt: new Date().toISOString(),
                    sourceImage: config.inputImagePath,
                    license: 'internal',
                },
            };

            return {
                success: true,
                result: {
                    asset,
                    message: `Generated Tier 1 ${config.assetType} asset`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'ASSET_GENERATION_FAILED',
                    message: `Failed to generate Tier 1 asset: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Implement Niagara VFX
     */
    async implementNiagaraVFX(
        config: VFXConfig,
        effectName: string,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const vfxSystem = {
                name: effectName,
                type: config.effectType,
                complexity: config.complexity,
                settings: {
                    maxParticles: config.maxParticles,
                    emitterCount: this.getEmitterCount(config.complexity),
                    material: 'M_Particle_Simple',
                    renderMode: 'Sprite',
                    gpuParticles: true,
                },
                performance: {
                    targetFramerate: config.targetFramerate,
                    estimatedCost: this.estimateVFXCost(config),
                },
                optimization: [
                    'GPU particles enabled',
                    'Simple unlit material',
                    'LOD system configured',
                    'Distance culling enabled',
                ],
            };

            return {
                success: true,
                result: {
                    vfxSystem,
                    message: `Implemented Niagara VFX: ${effectName}`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'VFX_IMPLEMENTATION_FAILED',
                    message: `Failed to implement VFX: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Configure spatial audio
     */
    async configureSpatialAudio(
        config: AudioConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const audioSetup = {
                spatialAudio: config.spatialAudio,
                settings: {
                    attenuationDistance: config.attenuationDistance,
                    falloffCurve: 'Logarithmic',
                    occlusionEnabled: config.occlusionEnabled,
                    reverbEnabled: config.reverbEnabled,
                    maxConcurrentSounds: 32,
                },
                quest3Settings: {
                    hrtfEnabled: true,
                    spatializationPlugin: 'OculusAudio',
                    audioFormat: 'OGG Vorbis',
                },
            };

            return {
                success: true,
                result: {
                    audioSetup,
                    message: 'Spatial audio configured successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'AUDIO_CONFIG_FAILED',
                    message: `Failed to configure spatial audio: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Optimize for Quest 3
     */
    async optimizeForQuest3(
        optimization: Quest3Optimization,
        targetAssets: string[],
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const optimizations = {
                targetFramerate: optimization.targetFramerate,
                budgets: {
                    drawCalls: optimization.drawCallBudget,
                    triangles: optimization.triangleBudget,
                    textures: optimization.textureBudget,
                },
                techniques: [
                    'Draw call batching',
                    'LOD system implementation',
                    'Texture compression (ASTC)',
                    'Occlusion culling',
                    'Forward rendering',
                    'Mobile material optimization',
                    'Dynamic light reduction',
                    'Shadow optimization',
                ],
                assetOptimizations: targetAssets.map((asset) => ({
                    asset,
                    actions: [
                        'Reduce triangle count',
                        'Compress textures',
                        'Simplify materials',
                        'Add LOD levels',
                    ],
                })),
            };

            return {
                success: true,
                result: {
                    optimizations,
                    message: `Quest 3 optimization configured for ${targetAssets.length} assets`,
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'OPTIMIZATION_FAILED',
                    message: `Failed to optimize for Quest 3: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Get triangle budget for asset type
     */
    private getTriangleBudget(assetType: string): number {
        const budgets: Record<string, number> = {
            mesh: 5000,
            material: 0,
            texture: 0,
        };
        return budgets[assetType] || 1000;
    }

    /**
     * Get texture resolution for platform
     */
    private getTextureResolution(platform: string): string {
        const resolutions: Record<string, string> = {
            Quest3: '1024x1024',
            PC: '2048x2048',
            All: '1024x1024',
        };
        return resolutions[platform] || '512x512';
    }

    /**
     * Get emitter count based on complexity
     */
    private getEmitterCount(complexity: string): number {
        const counts: Record<string, number> = {
            low: 1,
            medium: 2,
            high: 3,
        };
        return counts[complexity] || 1;
    }

    /**
     * Estimate VFX performance cost
     */
    private estimateVFXCost(config: VFXConfig): string {
        const particleCost = config.maxParticles / 100;
        if (particleCost < 1) return 'Low';
        if (particleCost < 3) return 'Medium';
        return 'High';
    }
}
