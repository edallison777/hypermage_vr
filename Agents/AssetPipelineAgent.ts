/**
 * AssetPipelineAgent - Asset import validation and provenance tracking
 * 
 * Responsibilities:
 * - Validate asset format and metadata
 * - Check for required provenance fields
 * - Block imports missing provenance
 * - Create and manage provenance records
 * - Track origin, license, cost, usage rights
 * - Maintain change history
 * - Recommend licensed assets without auto-purchasing
 * - Block automatic purchases and wait for manual approval
 * 
 * Requirements: 6.4, 6.5, 6.6, 16.1-16.4
 */

import { BaseAgent } from './BaseAgent.js';
import type {
    AgentConfig,
    AgentContext,
    AgentResult,
} from './types.js';
import type { IMCPAdapter } from '../MCP/types.js';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import * as fs from 'fs';
import * as path from 'path';

interface AssetSpec {
    id: string;
    name: string;
    tier: 0 | 1 | 2;
    type?: 'mesh' | 'texture' | 'material' | 'sound' | 'animation' | 'blueprint' | 'particle';
    provenance: ProvenanceRecord;
    unrealPath?: string;
    metadata?: Record<string, unknown>;
}

interface ProvenanceRecord {
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
}

interface ProvenanceChange {
    timestamp: string;
    actor: string;
    action: string;
    notes: string;
}

interface LicensedAssetRecommendation {
    assetId: string;
    assetName: string;
    source: string;
    sourceUrl: string;
    license: string;
    licenseUrl?: string;
    cost: number;
    currency: string;
    usageRights: {
        commercial: boolean;
        modification: boolean;
        redistribution: boolean;
    };
    description: string;
    requiresApproval: true;
    approved: false;
}

export class AssetPipelineAgent extends BaseAgent {
    private ajv: Ajv;
    private assetSchema: any;
    private provenanceRecords: Map<string, AssetSpec>;
    private changeHistory: Map<string, ProvenanceChange[]>;
    private licensedAssetRecommendations: LicensedAssetRecommendation[];

    constructor(config: AgentConfig, mcpAdapters: IMCPAdapter[] = []) {
        super(config, mcpAdapters);

        // Initialize JSON schema validator
        this.ajv = new Ajv({ allErrors: true, strict: false });
        addFormats(this.ajv);

        // Load AssetSpec schema
        const schemaPath = path.join(__dirname, '../Specs/schemas/AssetSpec.schema.json');
        this.assetSchema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
        this.ajv.addSchema(this.assetSchema, 'AssetSpec');

        // Initialize storage
        this.provenanceRecords = new Map();
        this.changeHistory = new Map();
        this.licensedAssetRecommendations = [];
    }

    protected getSystemPrompt(): string {
        return `You are the AssetPipelineAgent for the Unreal VR Multiplayer System.

Your responsibilities:
1. Validate asset imports for format and metadata correctness
2. Ensure all assets have complete provenance records
3. Block imports that are missing required provenance fields
4. Create and maintain provenance records for all assets
5. Track asset origin, license, cost, and usage rights
6. Maintain change history for all asset modifications
7. Recommend licensed assets when suitable
8. NEVER automatically purchase licensed assets
9. Always wait for manual approval before using licensed assets

Asset Tiers:
- Tier 0: Blockout primitives (cubes, spheres, basic shapes)
- Tier 1: Placeholder/generated assets from concept art
- Tier 2: Final/licensed assets from marketplaces

Required Provenance Fields:
- origin: generated | hand-crafted | licensed | marketplace
- license: License type (MIT, CC-BY-4.0, Commercial, Proprietary, etc.)
- createdAt: ISO 8601 timestamp
- createdBy: Agent or user name
- usageRights: { commercial, modification, redistribution }

Optional Provenance Fields:
- licenseUrl: URL to full license text
- sourceUrl: URL to original source
- cost: Cost in GBP if purchased
- approvedBy: User who approved the asset
- approvedAt: ISO 8601 timestamp of approval

When recommending licensed assets:
1. Identify suitable assets from marketplaces
2. Provide complete licensing details
3. Calculate total cost
4. Create recommendation record
5. Set requiresApproval: true
6. Set approved: false
7. Wait for manual approval before proceeding

Always respond with structured JSON that can be parsed by the orchestrator.`;
    }

    /**
     * Validate asset import
     * Checks format, metadata, and provenance completeness
     */
    async validateAssetImport(
        assetSpec: AssetSpec,
        _context: AgentContext
    ): Promise<AgentResult> {
        const startTime = Date.now();

        try {
            // Validate against schema
            const validate = this.ajv.getSchema('AssetSpec');
            if (!validate) {
                throw new Error('AssetSpec schema not loaded');
            }

            const valid = validate(assetSpec);
            if (!valid) {
                return {
                    success: false,
                    error: {
                        code: 'VALIDATION_ERROR',
                        message: 'Asset specification validation failed',
                        details: validate.errors,
                        retryable: false,
                    },
                    duration: Date.now() - startTime,
                };
            }

            // Check provenance completeness
            const provenanceCheck = this.checkProvenanceCompleteness(assetSpec.provenance);
            if (!provenanceCheck.complete) {
                return {
                    success: false,
                    error: {
                        code: 'INCOMPLETE_PROVENANCE',
                        message: 'Asset provenance is incomplete',
                        details: { missingFields: provenanceCheck.missingFields },
                        retryable: false,
                    },
                    duration: Date.now() - startTime,
                };
            }

            // For licensed assets, check approval
            if (
                (assetSpec.provenance.origin === 'licensed' ||
                    assetSpec.provenance.origin === 'marketplace') &&
                !assetSpec.provenance.approvedBy
            ) {
                return {
                    success: false,
                    error: {
                        code: 'APPROVAL_REQUIRED',
                        message: 'Licensed assets require manual approval before import',
                        details: {
                            assetId: assetSpec.id,
                            assetName: assetSpec.name,
                            license: assetSpec.provenance.license,
                            cost: assetSpec.provenance.cost,
                        },
                        retryable: false,
                    },
                    duration: Date.now() - startTime,
                };
            }

            return {
                success: true,
                result: {
                    valid: true,
                    assetId: assetSpec.id,
                    assetName: assetSpec.name,
                },
                duration: Date.now() - startTime,
            };
        } catch (error) {
            return {
                success: false,
                error: this.formatError(error),
                duration: Date.now() - startTime,
            };
        }
    }

    /**
     * Create provenance record for an asset
     */
    async createProvenanceRecord(
        assetSpec: AssetSpec,
        context: AgentContext
    ): Promise<AgentResult> {
        const startTime = Date.now();

        try {
            // Validate first
            const validationResult = await this.validateAssetImport(assetSpec, context);
            if (!validationResult.success) {
                return validationResult;
            }

            // Store provenance record
            this.provenanceRecords.set(assetSpec.id, assetSpec);

            // Initialize change history
            const initialChange: ProvenanceChange = {
                timestamp: new Date().toISOString(),
                actor: context.executionId || 'system',
                action: 'CREATED',
                notes: `Asset imported by ${assetSpec.provenance.createdBy}`,
            };
            this.changeHistory.set(assetSpec.id, [initialChange]);

            return {
                success: true,
                result: {
                    assetId: assetSpec.id,
                    provenanceRecordCreated: true,
                },
                duration: Date.now() - startTime,
            };
        } catch (error) {
            return {
                success: false,
                error: this.formatError(error),
                duration: Date.now() - startTime,
            };
        }
    }

    /**
     * Get provenance record for an asset
     */
    getProvenanceRecord(assetId: string): AssetSpec | undefined {
        return this.provenanceRecords.get(assetId);
    }

    /**
     * Get change history for an asset
     */
    getChangeHistory(assetId: string): ProvenanceChange[] {
        return this.changeHistory.get(assetId) || [];
    }

    /**
     * Recommend a licensed asset without purchasing
     */
    async recommendLicensedAsset(
        assetName: string,
        source: string,
        sourceUrl: string,
        license: string,
        cost: number,
        usageRights: { commercial: boolean; modification: boolean; redistribution: boolean },
        description: string,
        _context: AgentContext
    ): Promise<AgentResult> {
        const startTime = Date.now();

        try {
            const recommendation: LicensedAssetRecommendation = {
                assetId: `pending-${Date.now()}`,
                assetName,
                source,
                sourceUrl,
                license,
                cost,
                currency: 'GBP',
                usageRights,
                description,
                requiresApproval: true,
                approved: false,
            };

            // Store recommendation (DO NOT PURCHASE)
            this.licensedAssetRecommendations.push(recommendation);

            return {
                success: true,
                result: {
                    recommendation,
                    message:
                        'Licensed asset recommendation created. Manual approval required before purchase.',
                    nextSteps: [
                        'Review licensing terms',
                        'Verify usage rights match project needs',
                        'Approve purchase manually',
                        'Import asset after purchase',
                    ],
                },
                duration: Date.now() - startTime,
            };
        } catch (error) {
            return {
                success: false,
                error: this.formatError(error),
                duration: Date.now() - startTime,
            };
        }
    }

    /**
     * Get all pending licensed asset recommendations
     */
    getPendingRecommendations(): LicensedAssetRecommendation[] {
        return this.licensedAssetRecommendations.filter((r) => !r.approved);
    }

    /**
     * Check provenance completeness
     */
    private checkProvenanceCompleteness(provenance: ProvenanceRecord): {
        complete: boolean;
        missingFields: string[];
    } {
        const requiredFields = ['origin', 'license', 'createdAt', 'createdBy'];
        const missingFields: string[] = [];

        for (const field of requiredFields) {
            if (!provenance[field as keyof ProvenanceRecord]) {
                missingFields.push(field);
            }
        }

        // Check usageRights if present
        if (provenance.usageRights) {
            const usageRightsFields = ['commercial', 'modification', 'redistribution'];
            for (const field of usageRightsFields) {
                if (
                    typeof provenance.usageRights[
                    field as keyof typeof provenance.usageRights
                    ] !== 'boolean'
                ) {
                    missingFields.push(`usageRights.${field}`);
                }
            }
        }

        // For licensed/marketplace assets, require licenseUrl
        if (
            (provenance.origin === 'licensed' || provenance.origin === 'marketplace') &&
            !provenance.licenseUrl
        ) {
            missingFields.push('licenseUrl');
        }

        return {
            complete: missingFields.length === 0,
            missingFields,
        };
    }
}

/**
 * Create AssetPipelineAgent with default configuration
 */
export function createAssetPipelineAgent(mcpAdapters: IMCPAdapter[] = []): AssetPipelineAgent {
    const config: AgentConfig = {
        name: 'AssetPipelineAgent',
        description:
            'Validates asset imports, manages provenance records, and recommends licensed assets',
        capabilities: [
            {
                name: 'validate_asset_import',
                description: 'Validate asset format, metadata, and provenance completeness',
                parameters: {
                    assetSpec: 'AssetSpec object to validate',
                },
            },
            {
                name: 'create_provenance_record',
                description: 'Create and store provenance record for an asset',
                parameters: {
                    assetSpec: 'AssetSpec object with complete provenance',
                },
            },
            {
                name: 'recommend_licensed_asset',
                description: 'Recommend a licensed asset without auto-purchasing',
                parameters: {
                    assetName: 'Name of the asset',
                    source: 'Source marketplace or vendor',
                    sourceUrl: 'URL to asset listing',
                    license: 'License type',
                    cost: 'Cost in GBP',
                    usageRights: 'Usage rights object',
                    description: 'Asset description',
                },
            },
        ],
        model: {
            provider: 'bedrock',
            modelId: 'anthropic.claude-4-sonnet-20250514-v1:0',
            region: 'eu-west-1',
        },
    };

    return new AssetPipelineAgent(config, mcpAdapters);
}
