/**
 * Property-Based Test: Asset Provenance Completeness
 * 
 * Feature: unreal-vr-multiplayer-system
 * Property 10: Asset Provenance Completeness
 * 
 * For any asset in the system, a provenance record must exist containing origin, license,
 * licenseUrl (if applicable), createdAt, createdBy, and usageRights fields.
 * 
 * Validates: Requirements 6.5, 6.6
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

interface AssetSpec {
    id: string;
    name: string;
    tier: 0 | 1 | 2;
    type?: 'mesh' | 'texture' | 'material' | 'sound' | 'animation' | 'blueprint' | 'particle';
    provenance: {
        origin: 'generated' | 'hand-crafted' | 'licensed' | 'marketplace';
        license: string;
        licenseUrl?: string;
        createdAt: string;
        createdBy: string;
        sourceUrl?: string;
        cost?: number;
        approvedBy?: string;
        approvedAt?: string;
        usageRights?: {
            commercial: boolean;
            modification: boolean;
            redistribution: boolean;
        };
    };
    unrealPath?: string;
    metadata?: Record<string, unknown>;
}

describe('Feature: unreal-vr-multiplayer-system', () => {
    describe('Property 10: Asset Provenance Completeness', () => {
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

        // Generators for asset specifications
        const originArb = fc.constantFrom(
            'generated' as const,
            'hand-crafted' as const,
            'licensed' as const,
            'marketplace' as const
        );

        const licenseArb = fc.constantFrom(
            'MIT',
            'CC-BY-4.0',
            'Commercial',
            'Proprietary',
            'Apache-2.0',
            'GPL-3.0'
        );

        const usageRightsArb = fc.record({
            commercial: fc.boolean(),
            modification: fc.boolean(),
            redistribution: fc.boolean(),
        });

        const completeProvenanceArb = fc
            .tuple(originArb, licenseArb, usageRightsArb, fc.boolean())
            .map(([origin, license, usageRights, needsLicenseUrl]) => {
                const provenance: any = {
                    origin,
                    license,
                    licenseUrl:
                        needsLicenseUrl || origin === 'licensed' || origin === 'marketplace'
                            ? `https://example.com/licenses/${license.toLowerCase()}`
                            : undefined,
                    createdAt: new Date().toISOString(),
                    createdBy: 'TestAgent',
                    usageRights,
                };

                // Add approval for licensed/marketplace assets
                if (origin === 'licensed' || origin === 'marketplace') {
                    provenance.approvedBy = 'TestUser';
                    provenance.approvedAt = new Date().toISOString();
                }

                return provenance;
            });

        const completeAssetSpecArb = fc
            .tuple(
                fc.uuid(),
                fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0), // No whitespace-only strings
                fc.constantFrom(0 as const, 1 as const, 2 as const),
                completeProvenanceArb
            )
            .map(([id, name, tier, provenance]) => ({
                id,
                name,
                tier,
                provenance,
            }));

        it('should accept assets with complete provenance records', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    const result = await agent.validateAssetImport(assetSpec, context);
                    expect(result.success).toBe(true);
                }),
                { numRuns: 100 }
            );
        });

        it('should reject assets missing required provenance field: origin', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    const invalidSpec = {
                        ...assetSpec,
                        provenance: {
                            ...assetSpec.provenance,
                            origin: undefined as any,
                        },
                    };

                    const result = await agent.validateAssetImport(invalidSpec, context);
                    expect(result.success).toBe(false);
                    expect(result.error?.code).toMatch(/VALIDATION_ERROR|INCOMPLETE_PROVENANCE/);
                }),
                { numRuns: 50 }
            );
        });

        it('should reject assets missing required provenance field: license', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    const invalidSpec = {
                        ...assetSpec,
                        provenance: {
                            ...assetSpec.provenance,
                            license: undefined as any,
                        },
                    };

                    const result = await agent.validateAssetImport(invalidSpec, context);
                    expect(result.success).toBe(false);
                    expect(result.error?.code).toMatch(/VALIDATION_ERROR|INCOMPLETE_PROVENANCE/);
                }),
                { numRuns: 50 }
            );
        });

        it('should reject assets missing required provenance field: createdAt', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    const invalidSpec = {
                        ...assetSpec,
                        provenance: {
                            ...assetSpec.provenance,
                            createdAt: undefined as any,
                        },
                    };

                    const result = await agent.validateAssetImport(invalidSpec, context);
                    expect(result.success).toBe(false);
                    expect(result.error?.code).toMatch(/VALIDATION_ERROR|INCOMPLETE_PROVENANCE/);
                }),
                { numRuns: 50 }
            );
        });

        it('should reject assets missing required provenance field: createdBy', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    const invalidSpec = {
                        ...assetSpec,
                        provenance: {
                            ...assetSpec.provenance,
                            createdBy: undefined as any,
                        },
                    };

                    const result = await agent.validateAssetImport(invalidSpec, context);
                    expect(result.success).toBe(false);
                    expect(result.error?.code).toMatch(/VALIDATION_ERROR|INCOMPLETE_PROVENANCE/);
                }),
                { numRuns: 50 }
            );
        });

        it('should reject licensed/marketplace assets missing licenseUrl', () => {
            fc.assert(
                fc.asyncProperty(
                    fc.uuid(),
                    fc.string({ minLength: 1, maxLength: 50 }),
                    fc.constantFrom('licensed' as const, 'marketplace' as const),
                    licenseArb,
                    usageRightsArb,
                    async (id, name, origin, license, usageRights) => {
                        const assetSpec: AssetSpec = {
                            id,
                            name,
                            tier: 2,
                            provenance: {
                                origin,
                                license,
                                // Missing licenseUrl
                                createdAt: new Date().toISOString(),
                                createdBy: 'TestAgent',
                                usageRights,
                            },
                        };

                        const result = await agent.validateAssetImport(assetSpec, context);
                        expect(result.success).toBe(false);
                        expect(result.error?.code).toBe('INCOMPLETE_PROVENANCE');
                        expect((result.error?.details as any)?.missingFields).toContain('licenseUrl');
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should store provenance records for valid assets', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    // Create a fresh agent instance for this test to avoid state pollution
                    const freshAgent = createAssetPipelineAgent();
                    const result = await freshAgent.createProvenanceRecord(assetSpec, context);
                    expect(result.success).toBe(true);

                    // Verify record was stored
                    const storedRecord = freshAgent.getProvenanceRecord(assetSpec.id);
                    expect(storedRecord).toBeDefined();
                    expect(storedRecord?.id).toBe(assetSpec.id);
                    expect(storedRecord?.provenance.origin).toBe(assetSpec.provenance.origin);
                    expect(storedRecord?.provenance.license).toBe(assetSpec.provenance.license);
                    expect(storedRecord?.provenance.createdBy).toBe(assetSpec.provenance.createdBy);
                }),
                { numRuns: 100 }
            );
        });

        it('should maintain change history for assets', () => {
            fc.assert(
                fc.asyncProperty(completeAssetSpecArb, async (assetSpec) => {
                    // Create a fresh agent instance for this test to avoid state pollution
                    const freshAgent = createAssetPipelineAgent();
                    await freshAgent.createProvenanceRecord(assetSpec, context);

                    const history = freshAgent.getChangeHistory(assetSpec.id);
                    expect(history).toBeDefined();
                    expect(history.length).toBeGreaterThan(0);
                    expect(history[0].action).toBe('CREATED');
                    expect(history[0].timestamp).toBeDefined();
                }),
                { numRuns: 50 }
            );
        });

        it('should validate usageRights structure when present', () => {
            fc.assert(
                fc.asyncProperty(
                    completeAssetSpecArb,
                    fc.record({
                        commercial: fc.anything(),
                        modification: fc.anything(),
                        redistribution: fc.anything(),
                    }),
                    async (assetSpec, invalidUsageRights) => {
                        // Only test if at least one field is not a boolean
                        const hasInvalidField =
                            typeof invalidUsageRights.commercial !== 'boolean' ||
                            typeof invalidUsageRights.modification !== 'boolean' ||
                            typeof invalidUsageRights.redistribution !== 'boolean';

                        if (!hasInvalidField) {
                            return; // Skip this iteration
                        }

                        const invalidSpec = {
                            ...assetSpec,
                            provenance: {
                                ...assetSpec.provenance,
                                usageRights: invalidUsageRights as any,
                            },
                        };

                        const result = await agent.validateAssetImport(invalidSpec, context);
                        expect(result.success).toBe(false);
                    }
                ),
                { numRuns: 50 }
            );
        });

        it('should handle edge case: empty strings in provenance fields', () => {
            const assetSpec: AssetSpec = {
                id: '550e8400-e29b-41d4-a716-446655440000',
                name: 'Test Asset',
                tier: 1,
                provenance: {
                    origin: 'generated',
                    license: '', // Empty string
                    createdAt: new Date().toISOString(),
                    createdBy: '', // Empty string
                    usageRights: {
                        commercial: true,
                        modification: true,
                        redistribution: false,
                    },
                },
            };

            return agent.validateAssetImport(assetSpec, context).then((result) => {
                expect(result.success).toBe(false);
            });
        });

        it('should handle edge case: invalid ISO 8601 timestamp', () => {
            const assetSpec: AssetSpec = {
                id: '550e8400-e29b-41d4-a716-446655440000',
                name: 'Test Asset',
                tier: 1,
                provenance: {
                    origin: 'generated',
                    license: 'MIT',
                    createdAt: 'not-a-valid-timestamp',
                    createdBy: 'TestAgent',
                    usageRights: {
                        commercial: true,
                        modification: true,
                        redistribution: false,
                    },
                },
            };

            return agent.validateAssetImport(assetSpec, context).then((result) => {
                expect(result.success).toBe(false);
            });
        });
    });
});
