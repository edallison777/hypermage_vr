/**
 * Start Matchmaking Lambda — G5
 * Launches an ECS Fargate game server task and returns a ticket ID.
 * Replaces GameLift/FlexMatch with on-demand ECS.
 */

const { ECSClient, RunTaskCommand } = require('@aws-sdk/client-ecs');
const { DynamoDBClient, PutItemCommand } = require('@aws-sdk/client-dynamodb');
const crypto = require('crypto');

const ecs = new ECSClient({ region: process.env.AWS_REGION });
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION });

exports.handler = async (event) => {
    try {
        const body = JSON.parse(event.body || '{}');
        const { playerId } = body;

        if (!playerId) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'INVALID_REQUEST', message: 'playerId is required' })
            };
        }

        const taskResponse = await ecs.send(new RunTaskCommand({
            cluster: process.env.ECS_CLUSTER_ARN,
            taskDefinition: process.env.ECS_TASK_DEF_ARN,
            launchType: 'FARGATE',
            networkConfiguration: {
                awsvpcConfiguration: {
                    subnets: process.env.ECS_SUBNETS.split(','),
                    securityGroups: process.env.ECS_SECURITY_GROUPS.split(','),
                    assignPublicIp: 'ENABLED'
                }
            },
            count: 1
        }));

        if (!taskResponse.tasks || taskResponse.tasks.length === 0) {
            throw new Error('ECS RunTask returned no tasks: ' + JSON.stringify(taskResponse.failures || []));
        }

        const taskArn = taskResponse.tasks[0].taskArn;
        const ticketId = crypto.randomUUID();
        const ttl = Math.floor(Date.now() / 1000) + 3600;

        await dynamodb.send(new PutItemCommand({
            TableName: process.env.MATCHMAKING_TICKETS_TABLE,
            Item: {
                ticketId:  { S: ticketId },
                taskArn:   { S: taskArn },
                playerId:  { S: playerId },
                status:    { S: 'SEARCHING' },
                createdAt: { S: new Date().toISOString() },
                ttl:       { N: String(ttl) }
            }
        }));

        console.log(JSON.stringify({ level: 'INFO', message: 'Matchmaking started', ticketId, taskArn, playerId }));

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticketId, status: 'SEARCHING', startTime: new Date().toISOString() })
        };
    } catch (error) {
        console.error(JSON.stringify({ level: 'ERROR', message: error.message, stack: error.stack }));
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'MATCHMAKING_FAILED', message: error.message })
        };
    }
};
