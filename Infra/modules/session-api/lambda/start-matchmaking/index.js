/**
 * Start Matchmaking Lambda — G7
 * Joins an existing running ECS session if one exists; otherwise starts a new one.
 */

const { ECSClient, RunTaskCommand, ListTasksCommand, DescribeTasksCommand } = require('@aws-sdk/client-ecs');
const { EC2Client, DescribeNetworkInterfacesCommand } = require('@aws-sdk/client-ec2');
const { DynamoDBClient, PutItemCommand } = require('@aws-sdk/client-dynamodb');
const crypto = require('crypto');

const ecs      = new ECSClient({ region: process.env.AWS_REGION });
const ec2      = new EC2Client({ region: process.env.AWS_REGION });
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION });

const SERVER_PORT = 7777;

async function findRunningServer() {
    const list = await ecs.send(new ListTasksCommand({
        cluster: process.env.ECS_CLUSTER_ARN,
        desiredStatus: 'RUNNING'
    }));
    if (!list.taskArns || list.taskArns.length === 0) return null;

    const desc = await ecs.send(new DescribeTasksCommand({
        cluster: process.env.ECS_CLUSTER_ARN,
        tasks: [list.taskArns[0]]
    }));
    const task = desc.tasks?.[0];
    if (!task || task.lastStatus !== 'RUNNING') return null;

    const eni    = task.attachments?.find(a => a.type === 'ElasticNetworkInterface');
    const eniId  = eni?.details?.find(d => d.name === 'networkInterfaceId')?.value;
    if (!eniId) return null;

    const eniResp = await ec2.send(new DescribeNetworkInterfacesCommand({ NetworkInterfaceIds: [eniId] }));
    const ip      = eniResp.NetworkInterfaces?.[0]?.Association?.PublicIp;
    return ip ? { ip, taskArn: list.taskArns[0] } : null;
}

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

        const ttl      = Math.floor(Date.now() / 1000) + 3600;
        const ticketId = crypto.randomUUID();

        // Join an already-running server if one exists
        const running = await findRunningServer();
        if (running) {
            await dynamodb.send(new PutItemCommand({
                TableName: process.env.MATCHMAKING_TICKETS_TABLE,
                Item: {
                    ticketId:  { S: ticketId },
                    taskArn:   { S: running.taskArn },
                    playerId:  { S: playerId },
                    status:    { S: 'COMPLETED' },
                    createdAt: { S: new Date().toISOString() },
                    ttl:       { N: String(ttl) }
                }
            }));
            console.log(JSON.stringify({ level: 'INFO', message: 'Joined existing server', ticketId, ip: running.ip, playerId }));
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticketId,
                    status: 'COMPLETED',
                    gameSessionConnectionInfo: {
                        ipAddress: running.ip,
                        port: SERVER_PORT,
                        matchedPlayerSessions: [{ playerId, playerSessionId: running.taskArn }]
                    }
                })
            };
        }

        // No running server — start a new ECS task
        const taskResp = await ecs.send(new RunTaskCommand({
            cluster:       process.env.ECS_CLUSTER_ARN,
            taskDefinition: process.env.ECS_TASK_DEF_ARN,
            launchType:    'FARGATE',
            networkConfiguration: {
                awsvpcConfiguration: {
                    subnets:        process.env.ECS_SUBNETS.split(','),
                    securityGroups: process.env.ECS_SECURITY_GROUPS.split(','),
                    assignPublicIp: 'ENABLED'
                }
            },
            count: 1
        }));

        if (!taskResp.tasks || taskResp.tasks.length === 0) {
            throw new Error('ECS RunTask returned no tasks: ' + JSON.stringify(taskResp.failures || []));
        }

        const taskArn = taskResp.tasks[0].taskArn;
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

        console.log(JSON.stringify({ level: 'INFO', message: 'New server started', ticketId, taskArn, playerId }));
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
