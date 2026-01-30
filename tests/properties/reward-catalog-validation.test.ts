/**
 * Property-Based Test: Reward Catalog Validation
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 6: Reward Catalog Validation
 * 
 * For any reward grant operation, the reward ID must exist in the rewards_catalog.json file,
 * and operations with invalid reward IDs must be rejected with an error.
 * 
 * Validates: Requirements 5.3, 15.2, 15.3
 */

import fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';

interface Reward {
    id: string;
    name: string;
    description: string;
    category?: string;
}

interface RewardsCatalog {
    version: string;
    rewards: Reward[];
}

interface GrantRewardResult {
    success: boolean;
    error?: {
        code: string;
        message: string;
    };
}

// Load rewards catalog
function loadRewardsCatalog(): RewardsCatalog {
    const catalogPath = path.join(__dirname, '../../Specs/examples/rewards_catalog.json');
    const catalogContent = fs.readFileSync(catalogPath, 'utf8');
    return JSON.parse(catalogContent) as RewardsCatalog;
}

// Simulate reward granting (this will be replaced with actual implementation)
function grantReward(playerId: string, rewardId: string): GrantRewardResult {
    const catalog = loadRewardsCatalog();
    const rewardExists = catalog.rewards.some((r) => r.id === rewardId);

    if (rewardExists) {
        return { success: true };
    } else {
        return {
            success: false,
            error: {
                code: 'INVALID_REWARD_ID',
                message: `Reward ID '${rewardId}' not found in rewards catalog`,
            },
        };
    }
}

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 6: Reward Catalog Validation', () => {
        let catalog: RewardsCatalog;
        let validRewardIds: string[];

        beforeAll(() => {
            catalog = loadRewardsCatalog();
            validRewardIds = catalog.rewards.map((r) => r.id);
        });

        it('should accept valid reward IDs from the catalog', () => {
            fc.assert(
                fc.property(
                    fc.constantFrom(...validRewardIds),
                    fc.string({ minLength: 1, maxLength: 50 }), // playerId
                    (rewardId, playerId) => {
                        const result = grantReward(playerId, rewardId);
                        expect(result.success).toBe(true);
                        expect(result.error).toBeUndefined();
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should reject invalid reward IDs not in the catalog', () => {
            fc.assert(
                fc.property(
                    fc
                        .string({ minLength: 1, maxLength: 50 })
                        .filter((id) => !validRewardIds.includes(id)), // Generate IDs not in catalog
                    fc.string({ minLength: 1, maxLength: 50 }), // playerId
                    (rewardId, playerId) => {
                        const result = grantReward(playerId, rewardId);
                        expect(result.success).toBe(false);
                        expect(result.error).toBeDefined();
                        expect(result.error?.code).toBe('INVALID_REWARD_ID');
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should handle edge cases: empty strings, special characters', () => {
            const edgeCaseIds = ['', ' ', '!@#$%', 'reward_with_underscore', 'UPPERCASE_REWARD'];
            const playerId = 'test_player';

            edgeCaseIds.forEach((rewardId) => {
                const result = grantReward(playerId, rewardId);
                const isValid = validRewardIds.includes(rewardId);

                if (isValid) {
                    expect(result.success).toBe(true);
                } else {
                    expect(result.success).toBe(false);
                    expect(result.error?.code).toBe('INVALID_REWARD_ID');
                }
            });
        });

        it('should validate that all catalog rewards have required fields', () => {
            catalog.rewards.forEach((reward) => {
                expect(reward.id).toBeDefined();
                expect(typeof reward.id).toBe('string');
                expect(reward.id.length).toBeGreaterThan(0);

                expect(reward.name).toBeDefined();
                expect(typeof reward.name).toBe('string');
                expect(reward.name.length).toBeGreaterThan(0);

                expect(reward.description).toBeDefined();
                expect(typeof reward.description).toBe('string');
                expect(reward.description.length).toBeGreaterThan(0);
            });
        });

        it('should ensure no duplicate reward IDs in catalog', () => {
            const idSet = new Set<string>();
            const duplicates: string[] = [];

            catalog.rewards.forEach((reward) => {
                if (idSet.has(reward.id)) {
                    duplicates.push(reward.id);
                }
                idSet.add(reward.id);
            });

            expect(duplicates).toEqual([]);
        });
    });
});
