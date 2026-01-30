/**
 * SQLite Database for Orchestrator state persistence
 */

import Database from 'better-sqlite3';
import * as path from 'path';
import * as fs from 'fs';
import { ExecutionPlan, PlanExecution } from '../types';
import { logger } from '../utils/logger';

export class OrchestratorDatabase {
    private db: Database.Database;

    constructor(dbPath: string = 'orchestrator.db') {
        const dataDir = path.join(process.cwd(), 'data');
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }

        const fullPath = path.join(dataDir, dbPath);
        this.db = new Database(fullPath);
        this.initialize();
        logger.info('Database initialized', { path: fullPath });
    }

    private initialize(): void {
        this.db.exec(`
      CREATE TABLE IF NOT EXISTS plans (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        specification TEXT NOT NULL,
        context TEXT NOT NULL,
        steps TEXT NOT NULL,
        estimated_cost REAL NOT NULL,
        estimated_duration INTEGER NOT NULL,
        status TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        status TEXT NOT NULL,
        progress TEXT NOT NULL,
        steps TEXT NOT NULL,
        artifacts TEXT NOT NULL,
        costs TEXT NOT NULL,
        FOREIGN KEY (plan_id) REFERENCES plans(id)
      );

      CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
      CREATE INDEX IF NOT EXISTS idx_executions_plan_id ON executions(plan_id);
      CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
    `);
    }

    public savePlan(plan: ExecutionPlan): void {
        const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO plans 
      (id, created_at, specification, context, steps, estimated_cost, estimated_duration, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

        stmt.run(
            plan.id,
            plan.createdAt,
            plan.specification,
            JSON.stringify(plan.context),
            JSON.stringify(plan.steps),
            plan.estimatedCost,
            plan.estimatedDuration,
            plan.status
        );

        logger.info('Plan saved', { planId: plan.id });
    }

    public getPlan(planId: string): ExecutionPlan | null {
        const stmt = this.db.prepare('SELECT * FROM plans WHERE id = ?');
        const row = stmt.get(planId) as any;

        if (!row) return null;

        return {
            id: row.id,
            createdAt: row.created_at,
            specification: row.specification,
            context: JSON.parse(row.context),
            steps: JSON.parse(row.steps),
            estimatedCost: row.estimated_cost,
            estimatedDuration: row.estimated_duration,
            status: row.status,
        };
    }

    public saveExecution(execution: PlanExecution): void {
        const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO executions 
      (id, plan_id, start_time, end_time, status, progress, steps, artifacts, costs)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

        stmt.run(
            execution.id,
            execution.planId,
            execution.startTime,
            execution.endTime || null,
            execution.status,
            JSON.stringify(execution.progress),
            JSON.stringify(execution.steps),
            JSON.stringify(execution.artifacts),
            JSON.stringify(execution.costs)
        );

        logger.info('Execution saved', { executionId: execution.id });
    }

    public getExecution(executionId: string): PlanExecution | null {
        const stmt = this.db.prepare('SELECT * FROM executions WHERE id = ?');
        const row = stmt.get(executionId) as any;

        if (!row) return null;

        return {
            id: row.id,
            planId: row.plan_id,
            startTime: row.start_time,
            endTime: row.end_time,
            status: row.status,
            progress: JSON.parse(row.progress),
            steps: JSON.parse(row.steps),
            artifacts: JSON.parse(row.artifacts),
            costs: JSON.parse(row.costs),
        };
    }

    public close(): void {
        this.db.close();
        logger.info('Database closed');
    }
}
