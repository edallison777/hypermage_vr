#!/usr/bin/env node

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const fs = require('fs');
const path = require('path');

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

const SCHEMAS_DIR = path.join(__dirname, '..', 'Specs', 'schemas');
const EXAMPLES_DIR = path.join(__dirname, '..', 'Specs', 'examples');

const schemaFiles = [
    'LevelPlan.schema.json',
    'GameplayRules.schema.json',
    'AssetSpec.schema.json',
    'BudgetPolicy.schema.json',
    'DeploySpec.schema.json',
    'InteractionEvent.schema.json',
    'PlayerSessionSummary.schema.json',
    'CostModel.schema.json',
];

const exampleFiles = [
    { schema: 'LevelPlan.schema.json', example: 'LevelPlan.example.json' },
    { schema: 'GameplayRules.schema.json', example: 'GameplayRules.example.json' },
    { schema: 'AssetSpec.schema.json', example: 'AssetSpec.example.json' },
    { schema: 'BudgetPolicy.schema.json', example: 'BudgetPolicy.example.json' },
    { schema: 'DeploySpec.schema.json', example: 'DeploySpec.example.json' },
    { schema: 'InteractionEvent.schema.json', example: 'InteractionEvent.example.json' },
    { schema: 'PlayerSessionSummary.schema.json', example: 'PlayerSessionSummary.example.json' },
    { schema: 'CostModel.schema.json', example: 'CostModel.example.json' },
];

console.log('🔍 Validating JSON schemas...\n');

let hasErrors = false;

// Load all schemas
const schemas = {};
for (const schemaFile of schemaFiles) {
    const schemaPath = path.join(SCHEMAS_DIR, schemaFile);
    try {
        const schemaContent = fs.readFileSync(schemaPath, 'utf8');
        const schema = JSON.parse(schemaContent);
        schemas[schemaFile] = schema;
        ajv.addSchema(schema, schemaFile);
        console.log(`✅ Loaded schema: ${schemaFile}`);
    } catch (error) {
        console.error(`❌ Error loading schema ${schemaFile}:`, error.message);
        hasErrors = true;
    }
}

console.log('\n🔍 Validating example files against schemas...\n');

// Validate examples against schemas
for (const { schema: schemaFile, example: exampleFile } of exampleFiles) {
    const examplePath = path.join(EXAMPLES_DIR, exampleFile);

    try {
        const exampleContent = fs.readFileSync(examplePath, 'utf8');
        const exampleData = JSON.parse(exampleContent);

        const validate = ajv.getSchema(schemaFile);
        if (!validate) {
            console.error(`❌ Schema not found: ${schemaFile}`);
            hasErrors = true;
            continue;
        }

        const valid = validate(exampleData);

        if (valid) {
            console.log(`✅ ${exampleFile} validates against ${schemaFile}`);
        } else {
            console.error(`❌ ${exampleFile} validation failed:`);
            console.error(JSON.stringify(validate.errors, null, 2));
            hasErrors = true;
        }
    } catch (error) {
        console.error(`❌ Error validating ${exampleFile}:`, error.message);
        hasErrors = true;
    }
}

// Validate rewards catalog
console.log('\n🔍 Validating rewards catalog...\n');
const rewardsCatalogPath = path.join(EXAMPLES_DIR, 'rewards_catalog.json');
try {
    const catalogContent = fs.readFileSync(rewardsCatalogPath, 'utf8');
    const catalog = JSON.parse(catalogContent);

    if (!catalog.version || !catalog.rewards || !Array.isArray(catalog.rewards)) {
        console.error('❌ rewards_catalog.json: Invalid structure');
        hasErrors = true;
    } else {
        const rewardIds = new Set();
        for (const reward of catalog.rewards) {
            if (!reward.id || !reward.name || !reward.description) {
                console.error(`❌ rewards_catalog.json: Invalid reward entry`, reward);
                hasErrors = true;
            }
            if (rewardIds.has(reward.id)) {
                console.error(`❌ rewards_catalog.json: Duplicate reward ID: ${reward.id}`);
                hasErrors = true;
            }
            rewardIds.add(reward.id);
        }
        if (!hasErrors) {
            console.log(`✅ rewards_catalog.json is valid (${catalog.rewards.length} rewards)`);
        }
    }
} catch (error) {
    console.error('❌ Error validating rewards_catalog.json:', error.message);
    hasErrors = true;
}

console.log('\n' + '='.repeat(60));
if (hasErrors) {
    console.log('❌ Schema validation FAILED');
    process.exit(1);
} else {
    console.log('✅ All schemas and examples are valid!');
    process.exit(0);
}
