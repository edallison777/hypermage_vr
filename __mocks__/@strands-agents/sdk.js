/**
 * Manual mock for @strands-agents/sdk
 * Provides stub implementations of Agent and BedrockModel
 * to avoid ESM import.meta issues in Jest/CommonJS context.
 */

class Agent {
    constructor(config) {
        this.model = config.model;
        this.tools = config.tools || [];
        this.systemPrompt = config.systemPrompt || '';
    }

    async invoke(prompt) {
        return {
            lastMessage: `Mock response for: ${prompt}`,
        };
    }
}

class BedrockModel {
    constructor(config) {
        this.region = config.region;
        this.modelId = config.modelId;
        this.temperature = config.temperature;
        this.maxTokens = config.maxTokens;
    }
}

module.exports = {
    Agent,
    BedrockModel,
};
