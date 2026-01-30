/**
 * Property-Based Test: Licensed Asset Recommendation Without Purchase
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 9: Licensed Asset Recommendation Without Purchase
 * 
 * For any licensed asset identified as suitable, the system must create a recommendation record
 * with licensing details but must not execute any purchase API calls or add the asset to the
 * project without manual approval.
 * 
 * Validates: Requirements 6.4, 16.1, 16.2, 16.3, 16.4
 */

import fc from 'fast-check';
import { createAssetPipelineAgent } from '../../Agents/AssetPipelineAgent.js';
import type { AgentContext } from '../../Agents/types.js';

// Mock Strands SDK
jest.mock('@strands-agents/sdk', () => ({
    Agent: jest.fn().mockImplementation(() => ({
        invoke: jest.fn().mockResolvedValue({ lastMessage: 'Mock response' }),
    })),
    BedrockModel: jest.fn().mockImplementation(() => ({})),
}));

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 9: Licensed Asset Recommendation Without Purchase', () => {
        let agent: ReturnType<typeof createAssetPipelineAgent>;
        let context: AgentContext;

        beforeEach(() => {
            agent = createAssetPipelineAgent();
            context = {
                executionId: `exec-${Date.now()}`,
                planId: `plan-${Date.now()}`,
                stepId: `step-${Date.now()}`,
                environment: 'dev',
            };
        });

        // Generators for licensed asset recommendations
        const assetNameArb = fc.string({ minLength: 1, maxLength: 100 }).filter(s => s.trim().length > 0);
        const sourceArb = fc.constantFrom(
            'Unreal Marketplace',
            'TurboSquid',
            'Sketchfab',
            'Unity Asset Store',
            'CGTrader'
        );
        const sourceUrlArb = fc.webUrl();
        const licenseArb = fc.constantFrom(
            'Standard License',
            'Extended License',
            'Commercial License',
            'Editorial License',
            'Royalty-Free'
        );
        const costArb = fc.integer({ min: 1, max: 10000 }).map(n => n / 100); // £0.01 to £100.00
        const usageRightsArb = fc.record({
            commercial: fc.boolean(),
            modification: fc.boolean(),
            redistribution: fc.boolean(),
        });
        const descriptionArb = fc.string({ minLength: 10, maxLength: 500 });

        it('should create recommendation records for licensed assets', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        const result = await agent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        expect(result.success).toBe(true);
                        expect((result.result as any)).toBeDefined();
                        expect((result.result as any).recommendation).toBeDefined();
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should set requiresApproval to true for all licensed asset recommendations', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        const result = await agent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        expect((result.result as any).recommendation.requiresApproval).toBe(true);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should set approved to false for all new licensed asset recommendations', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        const result = await agent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        expect((result.result as any).recommendation.approved).toBe(false);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should include complete licensing details in recommendations', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        const result = await agent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        const rec = (result.result as any).recommendation;
                        expect(rec.assetName).toBe(assetName);
                        expect(rec.source).toBe(source);
                        expect(rec.sourceUrl).toBe(sourceUrl);
                        expect(rec.license).toBe(license);
                        expect(rec.cost).toBe(cost);
                        expect(rec.currency).toBe('GBP');
                        expect(rec.usageRights).toEqual(usageRights);
                        expect(rec.description).toBe(description);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it('should provide next steps guidance in recommendation response', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        const result = await agent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        expect((result.result as any).message).toBeDefined();
                        expect((result.result as any).message).toContain('Manual approval required');
                        expect((result.result as any).nextSteps).toBeDefined();
                        expect(Array.isArray((result.result as any).nextSteps)).toBe(true);
                        expect((result.result as any).nextSteps.length).toBeGreaterThan(0);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should track pending recommendations separately', () => {
            fc.assert(
                fc.asyncProperty(
                    assetNameArb,
                    sourceArb,
                    sourceUrlArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    descriptionArb,
                    async (assetName, source, sourceUrl, license, cost, usageRights, description) => {
                        // Create a fresh agent to avoid state pollution
                        const freshAgent = createAssetPipelineAgent();

                        await freshAgent.recommendLicensedAsset(
                            assetName,
                            source,
                            sourceUrl,
                            license,
                            cost,
                            usageRights,
                            description,
                            context
                        );

                        const pending = freshAgent.getPendingRecommendations();
                        expect(pending.length).toBe(1);
                        expect(pending[0].assetName).toBe(assetName);
                        expect(pending[0].approved).toBe(false);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should reject import of licensed assets without approval', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.uuid(),
                    assetNameArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    async (id, name, license, cost, usageRights) => {
                        const assetSpec = {
                            id,
                            name,
                            tier: 2 as const,
                            provenance: {
                                origin: 'licensed' as const,
                                license,
                                licenseUrl: 'https://example.com/license',
                                createdAt: new Date().toISOString(),
                                createdBy: 'TestAgent',
                                cost,
                                usageRights,
                                // Missing approvedBy - should be rejected
                            },
                        };

                        const result = await agent.validateAssetImport(assetSpec, context);
                        expect(result.success).toBe(false);
                        expect(result.error?.code).toBe('APPROVAL_REQUIRED');
                        expect(result.error?.message).toContain('manual approval');
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should accept import of licensed assets with approval', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.uuid(),
                    assetNameArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    async (id, name, license, cost, usageRights) => {
                        const assetSpec = {
                            id,
                            name,
                            tier: 2 as const,
                            provenance: {
                                origin: 'licensed' as const,
                                license,
                                licenseUrl: 'https://example.com/license',
                                createdAt: new Date().toISOString(),
                                createdBy: 'TestAgent',
                                cost,
                                usageRights,
                                approvedBy: 'TestUser',
                                approvedAt: new Date().toISOString(),
                            },
                        };

                        const result = await agent.validateAssetImport(assetSpec, context);
                        expect(result.success).toBe(true);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should handle edge case: zero cost licensed assets', () => {
            return agent
                .recommendLicensedAsset(
                    'Free Asset',
                    'Unreal Marketplace',
                    'https://example.com/asset',
                    'Free License',
                    0,
                    { commercial: true, modification: true, redistribution: false },
                    'A free asset from the marketplace',
                    context
                )
                .then((result) => {
                    expect(result.success).toBe(true);
                    expect((result.result as any).recommendation.cost).toBe(0);
                    expect((result.result as any).recommendation.requiresApproval).toBe(true);
                });
        });

        it('should handle edge case: very expensive licensed assets', () => {
            return agent
                .recommendLicensedAsset(
                    'Premium Asset Pack',
                    'TurboSquid',
                    'https://example.com/premium',
                    'Extended Commercial License',
                    9999.99,
                    { commercial: true, modification: true, redistribution: true },
                    'A very expensive premium asset pack',
                    context
                )
                .then((result) => {
                    expect(result.success).toBe(true);
                    expect((result.result as any).recommendation.cost).toBe(9999.99);
                    expect((result.result as any).recommendation.requiresApproval).toBe(true);
                });
        });

        it('should handle marketplace assets the same as licensed assets', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.uuid(),
                    assetNameArb,
                    licenseArb,
                    costArb,
                    usageRightsArb,
                    async (id, name, license, cost, usageRights) => {
                        const assetSpec = {
                            id,
                            name,
                            tier: 2 as const,
                            provenance: {
                                origin: 'marketplace' as const,
                                license,
                                licenseUrl: 'https://example.com/license',
                                createdAt: new Date().toISOString(),
                                createdBy: 'TestAgent',
                                cost,
                                usageRights,
                                // Missing approvedBy - should be rejected
                            },
                        };

                        const result = await agent.validateAssetImport(assetSpec, context);
                        expect(result.success).toBe(false);
                        expect(result.error?.code).toBe('APPROVAL_REQUIRED');
                    }
                ),
                { numRuns: 50 }
            );
        });
    });
});
