/**
 * Orchestrator Service Entry Point
 */

import { OrchestratorServer } from './api/server';
import { logger } from './utils/logger';

const PORT = parseInt(process.env.PORT || '3000', 10);

async function main(): Promise<void> {
    try {
        logger.info('Starting Orchestrator service...');

        const server = new OrchestratorServer(PORT);
        server.start();

        logger.info('Orchestrator service started successfully');
    } catch (error) {
        logger.error('Failed to start Orchestrator service', { error });
        process.exit(1);
    }
}

// Handle graceful shutdown
process.on('SIGTERM', () => {
    logger.info('SIGTERM received, shutting down gracefully');
    process.exit(0);
});

process.on('SIGINT', () => {
    logger.info('SIGINT received, shutting down gracefully');
    process.exit(0);
});

main().catch((error) => {
    logger.error('Unhandled error in main', { error });
    process.exit(1);
});
