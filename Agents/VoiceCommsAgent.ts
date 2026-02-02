/**
 * VoiceCommsAgent
 * 
 * Responsible for implementing party voice chat integration and
 * mute/block controls for multiplayer VR gameplay.
 */

import { BaseAgent } from './BaseAgent.js';
import type { AgentConfig, AgentContext, AgentResult } from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';

export interface VoiceConfig {
    provider: 'unreal-voice-chat' | 'vivox' | 'mock';
    channelType: 'party' | 'proximity' | 'team';
    codec: 'opus' | 'pcm';
    bitrate: number; // kbps
    sampleRate: number; // Hz
}

export interface MuteBlockConfig {
    enableMute: boolean;
    enableBlock: boolean;
    persistBlocks: boolean;
    muteIndicator: boolean;
}

export class VoiceCommsAgent extends BaseAgent {
    constructor(mcpAdapters: IMCPAdapter[] = []) {
        const config: AgentConfig = {
            name: 'voice-comms',
            description: 'Implements party voice chat and mute/block controls',
            capabilities: [
                {
                    name: 'implement_party_voice',
                    description: 'Implement party voice chat for all players in shard',
                    parameters: {
                        type: 'object',
                        required: ['voiceConfig'],
                        properties: {
                            voiceConfig: {
                                type: 'object',
                                description: 'Voice chat configuration',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'implement_mute_controls',
                    description: 'Implement player mute and block functionality',
                    parameters: {
                        type: 'object',
                        required: ['muteBlockConfig'],
                        properties: {
                            muteBlockConfig: {
                                type: 'object',
                                description: 'Mute/block configuration',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'implement_voice_ui',
                    description: 'Implement VR UI for voice controls',
                    parameters: {
                        type: 'object',
                        required: ['uiStyle'],
                        properties: {
                            uiStyle: {
                                type: 'string',
                                description: 'UI style (minimal, standard, detailed)',
                            },
                        },
                    },
                    mcpAdapters: ['UnrealMCP'],
                },
                {
                    name: 'configure_voice_provider',
                    description: 'Configure voice provider integration',
                    parameters: {
                        type: 'object',
                        required: ['provider'],
                        properties: {
                            provider: {
                                type: 'string',
                                description: 'Voice provider name',
                            },
                            credentials: {
                                type: 'object',
                                description: 'Provider credentials (optional)',
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
        return `You are the VoiceCommsAgent, responsible for implementing party voice chat and player controls.

Your responsibilities:

1. **Party Voice Integration**: Implement voice chat for all players in shard:
   - Use Unreal Voice Chat Interface plugin
   - Create party channel for each shard
   - Route audio to all players in shard (non-spatial)
   - Support pluggable voice providers:
     * Unreal Voice Chat (default)
     * Vivox (optional)
     * Mock provider (testing)
   - Handle voice connection lifecycle:
     * Connect on player join
     * Disconnect on player leave
     * Reconnect on network issues
   - Audio quality settings:
     * Codec: Opus (recommended for bandwidth)
     * Bitrate: 24-32 kbps per player
     * Sample rate: 16 kHz (sufficient for voice)
   - Total bandwidth: ~300-500 kbps for 15 players

2. **Mute/Block Controls**: Implement player moderation:
   - Mute functionality:
     * Local mute (client-side audio filtering)
     * Mute indicator visible to muted player
     * Persistent mute across sessions (optional)
     * Unmute capability
   - Block functionality:
     * Prevent voice communication
     * Prevent text chat (if implemented)
     * Persist blocks to player profile
     * Unblock capability
   - Server-side enforcement:
     * Validate mute/block requests
     * Prevent abuse (rate limiting)
     * Log moderation actions

3. **Voice UI**: Implement VR-friendly voice controls:
   - Minimal UI style (default):
     * Speaking indicator (small icon)
     * Mute button (wrist menu)
     * Player list with mute/block options
   - VR interaction:
     * Hand-tracked UI (Quest 3)
     * Gaze-based selection (fallback)
     * Voice commands (optional)
   - Visual feedback:
     * Speaking indicator (animated)
     * Muted indicator (icon)
     * Connection status (color-coded)

4. **Voice Provider Configuration**: Support multiple providers:
   - Unreal Voice Chat Interface:
     * Built-in Unreal plugin
     * No external dependencies
     * Good for prototyping
   - Vivox:
     * Enterprise-grade solution
     * Requires credentials
     * Better quality and features
   - Mock Provider:
     * Testing only
     * No actual audio transmission
     * Simulates connection events

Key Principles:
- Party voice (all players hear each other)
- No spatial audio or proximity-based voice
- Client-side mute for immediate feedback
- Server-side block for persistent moderation
- Minimize bandwidth usage (Quest 3 wireless)
- Provide clear visual feedback
- Handle network issues gracefully
- Respect player privacy and comfort

C++ Implementation Guidelines:
- Use IVoiceChatUser interface for player voice
- Use IVoiceChat interface for voice system
- Implement UVoiceComponent for player voice state
- Use UPROPERTY(Replicated) for mute/block state
- Use UFUNCTION(Server, Reliable) for moderation actions
- Handle voice provider initialization in GameInstance
- Clean up voice connections on player leave

Audio Quality vs Bandwidth:
- 24 kbps: Good quality, low bandwidth (recommended)
- 32 kbps: Better quality, moderate bandwidth
- 48 kbps: High quality, higher bandwidth (not recommended for Quest 3)

Output Format:
Return structured JSON with:
- Voice provider configuration
- Channel setup details
- Mute/block implementation
- UI component specifications
- Bandwidth calculations
- Integration instructions

Be precise with audio settings and bandwidth estimates.`;
    }

    /**
     * Implement party voice chat
     */
    async implementPartyVoice(
        config: VoiceConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const implementation = {
                provider: config.provider,
                channelType: 'party',
                audioSettings: {
                    codec: config.codec,
                    bitrate: config.bitrate,
                    sampleRate: config.sampleRate,
                },
                bandwidthEstimate: this.calculateVoiceBandwidth(config.bitrate, 15),
                components: [
                    {
                        name: 'VoiceComponent',
                        class: 'UVoiceComponent',
                        features: [
                            'Voice connection management',
                            'Speaking detection',
                            'Audio routing',
                            'Connection status tracking',
                        ],
                    },
                    {
                        name: 'VoiceChannelManager',
                        class: 'UVoiceChannelManager',
                        features: [
                            'Party channel creation',
                            'Player join/leave handling',
                            'Channel lifecycle management',
                        ],
                    },
                ],
            };

            return {
                success: true,
                result: {
                    implementation,
                    message: 'Party voice chat implemented successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'VOICE_IMPLEMENTATION_FAILED',
                    message: `Failed to implement party voice: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Implement mute/block controls
     */
    async implementMuteControls(
        config: MuteBlockConfig,
        context: AgentContext
    ): Promise<AgentResult> {
        try {
            const implementation = {
                muteFeatures: config.enableMute ? [
                    'Client-side audio filtering',
                    'Mute indicator UI',
                    'Persistent mute (optional)',
                    'Unmute capability',
                ] : [],
                blockFeatures: config.enableBlock ? [
                    'Server-side block enforcement',
                    'Persistent block storage',
                    'Block list management',
                    'Unblock capability',
                ] : [],
                components: [
                    {
                        name: 'MuteBlockComponent',
                        class: 'UMuteBlockComponent',
                        features: [
                            'Mute/block state management',
                            'Server validation',
                            'Persistence handling',
                        ],
                    },
                ],
                config,
            };

            return {
                success: true,
                result: {
                    implementation,
                    message: 'Mute/block controls implemented successfully',
                },
                duration: 0,
            };
        } catch (error) {
            return {
                success: false,
                error: {
                    code: 'MUTE_BLOCK_FAILED',
                    message: `Failed to implement mute/block controls: ${error}`,
                },
                duration: 0,
            };
        }
    }

    /**
     * Calculate voice bandwidth for N players
     */
    private calculateVoiceBandwidth(bitratePerPlayer: number, playerCount: number): {
        perPlayer: string;
        total: string;
        recommendation: string;
    } {
        const totalKbps = bitratePerPlayer * (playerCount - 1); // Each player receives from N-1 others
        const totalMbps = totalKbps / 1000;

        let recommendation = 'Good';
        if (totalMbps > 0.5) {
            recommendation = 'High - consider reducing bitrate';
        } else if (totalMbps < 0.3) {
            recommendation = 'Excellent - low bandwidth usage';
        }

        return {
            perPlayer: `${bitratePerPlayer} kbps`,
            total: `${totalKbps} kbps (${totalMbps.toFixed(2)} Mbps)`,
            recommendation,
        };
    }
}
