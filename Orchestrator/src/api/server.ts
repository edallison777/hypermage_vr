/**
 * Orchestrator HTTP API Server
 * 
 * Provides REST API for plan creation and execution
 */

import express, { Express, Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';
import { PlanGenerator } from '../services/PlanGenerator';
import { PlanExecutor } from '../services/PlanExecutor';
import { OrchestratorDatabase } from '../database/Database';
import {
    CreatePlanRequest,
    CreatePlanResponse,
    ExecutePlanRequest,
    ExecutePlanResponse,
    ExecutionStatusResponse,
} from '../types';

export class OrchestratorServer {
    private app: Express;
    private port: number;
    private planGenerator: PlanGenerator;
    private planExecutor: PlanExecutor;
    private database: OrchestratorDatabase;

    constructor(port: number = 3000) {
        this.app = express();
        this.port = port;
        this.planGenerator = new PlanGenerator();
        this.planExecutor = new PlanExecutor();
        this.database = new OrchestratorDatabase();
        this.setupMiddleware();
        this.setupRoutes();
        this.setupErrorHandling();
    }

    private setupMiddleware(): void {
        this.app.use(express.json());
        this.app.use(express.urlencoded({ extended: true }));

        // Request logging
        this.app.use((req: Request, res: Response, next: NextFunction) => {
            logger.info('Incoming request', {
                method: req.method,
                path: req.path,
                query: req.query,
                body: req.body,
            });
            next();
        });

        // CORS for local development
        this.app.use((req: Request, res: Response, next: NextFunction) => {
            res.header('Access-Control-Allow-Origin', '*');
            res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
            if (req.method === 'OPTIONS') {
                res.sendStatus(200);
            } else {
                next();
            }
        });
    }

    private setupRoutes(): void {
        // Health check
        this.app.get('/health', (req: Request, res: Response) => {
            res.json({ status: 'ok', timestamp: new Date().toISOString() });
        });

        // API v1 routes
        const apiV1 = express.Router();

        // POST /api/v1/plans - Create execution plan
        apiV1.post('/plans', async (req: Request, res: Response, next: NextFunction) => {
            try {
                const request: CreatePlanRequest = req.body;

                // TODO: Implement plan generation
                const response: CreatePlanResponse = {
                    planId: 'mock-plan-id',
                    steps: [],
                    estimatedCost: 0,
                    estimatedDuration: '0h',
                };

                logger.info('Plan created', { planId: response.planId });
                res.status(201).json(response);
            } catch (error) {
                next(error);
            }
        });

        // GET /api/v1/plans/:planId - Get plan details
        apiV1.get('/plans/:planId', async (req: Request, res: Response, next: NextFunction) => {
            try {
                const { planId } = req.params;

                // TODO: Implement plan retrieval
                logger.info('Plan retrieved', { planId });
                res.json({ planId, status: 'pending' });
            } catch (error) {
                next(error);
            }
        });

        // POST /api/v1/plans/:planId/execute - Execute plan
        apiV1.post(
            '/plans/:planId/execute',
            async (req: Request, res: Response, next: NextFunction) => {
                try {
                    const { planId } = req.params;
                    const request: ExecutePlanRequest = req.body;

                    if (!request.approved) {
                        res.status(400).json({ error: 'Plan must be approved before execution' });
                        return;
                    }

                    // TODO: Implement plan execution
                    const response: ExecutePlanResponse = {
                        executionId: 'mock-execution-id',
                        status: 'running',
                        progress: {
                            completed: 0,
                            total: 0,
                            currentStep: 'initializing',
                        },
                    };

                    logger.info('Plan execution started', { planId, executionId: response.executionId });
                    res.status(202).json(response);
                } catch (error) {
                    next(error);
                }
            }
        );

        // GET /api/v1/executions/:executionId - Get execution status
        apiV1.get(
            '/executions/:executionId',
            async (req: Request, res: Response, next: NextFunction) => {
                try {
                    const { executionId } = req.params;

                    // TODO: Implement execution status retrieval
                    const response: ExecutionStatusResponse = {
                        executionId,
                        planId: 'mock-plan-id',
                        status: 'running',
                        steps: [],
                        artifacts: [],
                        costs: {
                            totalCost: 0,
                            currency: 'GBP',
                            byService: {},
                            byStep: {},
                        },
                    };

                    logger.info('Execution status retrieved', { executionId });
                    res.json(response);
                } catch (error) {
                    next(error);
                }
            }
        );

        // POST /api/v1/executions/:executionId/pause - Pause execution
        apiV1.post(
            '/executions/:executionId/pause',
            async (req: Request, res: Response, next: NextFunction) => {
                try {
                    const { executionId } = req.params;

                    // TODO: Implement execution pause
                    logger.info('Execution paused', { executionId });
                    res.json({ executionId, status: 'paused' });
                } catch (error) {
                    next(error);
                }
            }
        );

        // POST /api/v1/executions/:executionId/resume - Resume execution
        apiV1.post(
            '/executions/:executionId/resume',
            async (req: Request, res: Response, next: NextFunction) => {
                try {
                    const { executionId } = req.params;

                    // TODO: Implement execution resume
                    logger.info('Execution resumed', { executionId });
                    res.json({ executionId, status: 'running' });
                } catch (error) {
                    next(error);
                }
            }
        );

        this.app.use('/api/v1', apiV1);
    }

    private setupErrorHandling(): void {
        // 404 handler
        this.app.use((req: Request, res: Response) => {
            res.status(404).json({
                error: 'Not Found',
                message: `Route ${req.method} ${req.path} not found`,
            });
        });

        // Error handler
        this.app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
            logger.error('Request error', {
                error: err.message,
                stack: err.stack,
                path: req.path,
                method: req.method,
            });

            res.status(500).json({
                error: 'Internal Server Error',
                message: err.message,
            });
        });
    }

    public start(): void {
        this.app.listen(this.port, () => {
            logger.info(`Orchestrator API server started on port ${this.port}`);
        });
    }

    public getApp(): Express {
        return this.app;
    }
}
