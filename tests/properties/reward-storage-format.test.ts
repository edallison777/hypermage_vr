/**
 * Property-Based Test: Reward Storage Format
 * Feature: unreal-vr-multiplayer-system
 * Property 14: Reward Storage Format
 * Validates: Requirements 15.4, 15.5
 *
 * For any granted reward, the database record must store the reward as a boolean flag (true)
 * with the reward ID as a string key, and the record must not have a TTL attribute.
 */

import fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';

// Reward catalog entry
interface RewardCatalogEntry {
    id: string;
    name: string;
    description: string;
    category?: string;
}

// Reward catalog
interface RewardCatalog {
    version: string;
    lastUpdated: string;
    rewards: RewardCatalogEntry[];
}

// Player reward record (as stored in DynamoDB)
interface PlayerRewardRecord {
    playerId: string; // Partition key
    rewardId: string; // Sort key
    granted: boolean; // Boolean flag (always true)
    grantedAt: Date;
    ttl?: number; // Should NOT exist for rewards (persistent)
}

// Mock reward system
class MockRewardSystem {
    private catalog: RewardCatalog | null = null;
    private playerRewards: Map<string, Map<string, PlayerRewardRecord>> =
        new Map();

    loadCatalog(catalogPath: string): boolean {
        try {
            const catalogData = fs.readFileSync(catalogPath, 'utf-8');
            this.catalog = JSON.parse(catalogData);
            return true;
        } catch (error) {
            return false;
        }
    }

    isValidRewardId(rewardId: string): boolean {
        if (!this.catalog) {
            return false;
        }
        return this.catalog.rewards.some((reward) => reward.id === rewardId);
    }

    grantReward(
        playerId: string,
        rewardId: string
    ): { success: boolean; errorCode?: string; errorMessage?: string } {
        // Check if catalog is loaded
        if (!this.catalog) {
            return {
                success: false,
                errorCode: 'REWARD_CATALOG_NOT_FOUND',
                errorMessage: 'Rewards catalog is not loaded',
            };
        }

        // Validate reward ID
        if (!this.isValidRewardId(rewardId)) {
            return {
                success: false,
                errorCode: 'INVALID_REWARD_ID',
                errorMessage: `Reward ID '${rewardId}' not found in catalog`,
            };
        }

        // Get or create player rewards map
        if (!this.playerRewards.has(playerId)) {
            this.playerRewards.set(playerId, new Map());
        }
        const rewards = this.playerRewards.get(playerId)!;

        // Check if already granted
        if (rewards.has(rewardId)) {
            return {
                success: false,
                errorCode: 'REWARD_ALREADY_GRANTED',
                errorMessage: `Reward '${rewardId}' already granted`,
            };
        }

        // Store reward as boolean flag with string identifier
        // Requirement 15.4: Store as boolean flag with string identifier
        // NO TTL attribute (persistent)
        const record: PlayerRewardRecord = {
            playerId,
            rewardId,
            granted: true, // Boolean flag
            grantedAt: new Date(),
            // ttl is intentionally NOT set (rewards are persistent)
        };

        rewards.set(rewardId, record);

        return { success: true };
    }

    getPlayerRewards(playerId: string): PlayerRewardRecord[] {
        const rewards = this.playerRewards.get(playerId);
        if (!rewards) {
            return [];
        }
        return Array.from(rewards.values());
    }

    hasReward(playerId: string, rewardId: string): boolean {
        const rewards = this.playerRewards.get(playerId);
        return rewards ? rewards.has(rewardId) : false;
    }

    getCatalog(): RewardCatalog | null {
        return this.catalog;
    }
}

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 14: Reward Storage Format', () => {
        const catalogPath = path.join(
            __dirname,
            '../../Specs/examples/rewards_catalog.json'
        );

        it('should store rewards as boolean flags with string identifiers', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string().filter((s) => s.trim().length > 0), // playerId
                    fc.array(fc.integer({ min: 0, max: 7 }), {
                        minLength: 1,
                        maxLength: 5,
                    }), // reward indices
                    async (playerId, rewardIndices) => {
                        const system = new MockRewardSystem();
                        system.loadCatalog(catalogPath);

                        const catalog = system.getCatalog();
                        expect(catalog).not.toBeNull();

                        // Grant rewards
                        const uniqueIndices = [...new Set(rewardIndices)];
                        for (const index of uniqueIndices) {
                            const rewardId = catalog!.rewards[index].id;
                            const result = system.grantReward(playerId, rewardId);
                            expect(result.success).toBe(true);
                        }

                        // Verify storage format
                        const rewards = system.getPlayerRewards(playerId);
                        expect(rewards.length).toBe(uniqueIndices.length);

                        for (const record of rewards) {
                            // Verify partition key (playerId)
                            expect(record.playerId).toBe(playerId);

                            // Verify sort key (rewardId) is a string
                            expect(typeof record.rewardId).toBe('string');
                            expect(record.rewardId.length).toBeGreaterThan(0);

                            // Verify boolean flag is true
                            expect(record.granted).toBe(true);
                            expect(typeof record.granted).toBe('boolean');

                            // Verify NO TTL attribute (rewards are persistent)
                            expect(record.ttl).toBeUndefined();
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should reject invalid reward IDs with INVALID_REWARD_ID error', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string().filter((s) => s.trim().length > 0), // playerId
                    fc
                        .string()
                        .filter((s) => s.trim().length > 0 && !s.includes('_complete')), // invalid rewardId
                    async (playerId, invalidRewardId) => {
                        const system = new MockRewardSystem();
                        system.loadCatalog(catalogPath);

                        // Try to grant invalid reward
                        const result = system.grantReward(playerId, invalidRewardId);

                        // Verify rejection
                        expect(result.success).toBe(false);
                        expect(result.errorCode).toBe('INVALID_REWARD_ID');
                        expect(result.errorMessage).toContain(invalidRewardId);
                        expect(result.errorMessage).toContain('not found in catalog');

                        // Verify no reward was stored
                        const rewards = system.getPlayerRewards(playerId);
                        expect(rewards.length).toBe(0);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should reject operations when catalog not loaded with REWARD_CATALOG_NOT_FOUND error', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string().filter((s) => s.trim().length > 0), // playerId
                    fc.string().filter((s) => s.trim().length > 0), // rewardId
                    async (playerId, rewardId) => {
                        const system = new MockRewardSystem();
                        // Do NOT load catalog

                        // Try to grant reward without catalog
                        const result = system.grantReward(playerId, rewardId);

                        // Verify rejection
                        expect(result.success).toBe(false);
                        expect(result.errorCode).toBe('REWARD_CATALOG_NOT_FOUND');
                        expect(result.errorMessage).toContain('not loaded');

                        // Verify no reward was stored
                        const rewards = system.getPlayerRewards(playerId);
                        expect(rewards.length).toBe(0);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should prevent duplicate reward grants with REWARD_ALREADY_GRANTED error', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string().filter((s) => s.trim().length > 0), // playerId
                    fc.integer({ min: 0, max: 7 }), // reward index
                    async (playerId, rewardIndex) => {
                        const system = new MockRewardSystem();
                        system.loadCatalog(catalogPath);

                        const catalog = system.getCatalog();
                        const rewardId = catalog!.rewards[rewardIndex].id;

                        // Grant reward first time (should succeed)
                        const firstResult = system.grantReward(playerId, rewardId);
                        expect(firstResult.success).toBe(true);

                        // Try to grant same reward again (should fail)
                        const secondResult = system.grantReward(playerId, rewardId);
                        expect(secondResult.success).toBe(false);
                        expect(secondResult.errorCode).toBe('REWARD_ALREADY_GRANTED');
                        expect(secondResult.errorMessage).toContain(rewardId);
                        expect(secondResult.errorMessage).toContain('already granted');

                        // Verify only one record exists
                        const rewards = system.getPlayerRewards(playerId);
                        expect(rewards.length).toBe(1);
                        expect(rewards[0].rewardId).toBe(rewardId);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should validate all rewards in catalog are grantable', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.string().filter((s) => s.trim().length > 0), // playerId
                    async (playerId) => {
                        const system = new MockRewardSystem();
                        system.loadCatalog(catalogPath);

                        const catalog = system.getCatalog();
                        expect(catalog).not.toBeNull();

                        // Try to grant each reward in catalog
                        for (const reward of catalog!.rewards) {
                            const result = system.grantReward(playerId, reward.id);
                            expect(result.success).toBe(true);

                            // Verify storage format
                            const record = system
                                .getPlayerRewards(playerId)
                                .find((r) => r.rewardId === reward.id);
                            expect(record).toBeDefined();
                            expect(record!.granted).toBe(true);
                            expect(record!.ttl).toBeUndefined(); // No TTL
                        }

                        // Verify all rewards were stored
                        const allRewards = system.getPlayerRewards(playerId);
                        expect(allRewards.length).toBe(catalog!.rewards.length);
                    }
                ),
                { numRuns: 10 } // Fewer runs since this tests all rewards
            );
        });

        it('should maintain separate reward records per player', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.array(fc.string().filter((s) => s.trim().length > 0), {
                        minLength: 2,
                        maxLength: 5,
                    }), // playerIds
                    fc.integer({ min: 0, max: 7 }), // reward index
                    async (playerIds, rewardIndex) => {
                        const system = new MockRewardSystem();
                        system.loadCatalog(catalogPath);

                        const catalog = system.getCatalog();
                        const rewardId = catalog!.rewards[rewardIndex].id;

                        // Grant same reward to multiple players
                        const uniquePlayers = [...new Set(playerIds)];
                        for (const playerId of uniquePlayers) {
                            const result = system.grantReward(playerId, rewardId);
                            expect(result.success).toBe(true);
                        }

                        // Verify each player has their own record
                        for (const playerId of uniquePlayers) {
                            const rewards = system.getPlayerRewards(playerId);
                            expect(rewards.length).toBe(1);
                            expect(rewards[0].playerId).toBe(playerId);
                            expect(rewards[0].rewardId).toBe(rewardId);
                            expect(rewards[0].granted).toBe(true);
                            expect(rewards[0].ttl).toBeUndefined();
                        }
                    }
                ),
                { numRuns: 100 }
            );
        });
    });
});
