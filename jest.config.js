module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
    roots: ['<rootDir>/tests', '<rootDir>/Orchestrator', '<rootDir>/Agents', '<rootDir>/MCP'],
    testMatch: ['**/*.test.ts', '**/*.spec.ts'],
    collectCoverageFrom: [
        '**/*.ts',
        '!**/*.d.ts',
        '!**/node_modules/**',
        '!**/dist/**',
        '!**/*.test.ts',
        '!**/*.spec.ts',
    ],
    coverageThreshold: {
        global: {
            branches: 80,
            functions: 80,
            lines: 80,
            statements: 80,
        },
    },
    moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
    moduleNameMapper: {
        '^(\\.{1,2}/.*)\\.js$': '$1',
        '^@strands-agents/sdk$': '<rootDir>/__mocks__/@strands-agents/sdk.js',
    },
    transformIgnorePatterns: [
        'node_modules/(?!(@strands-agents|@aws-sdk)/)',
    ],
    transform: {
        '^.+\\.[tj]sx?$': ['ts-jest', {
            tsconfig: 'tsconfig.json',
        }],
    },
};
