/**
 * Get Matchmaking Status Lambda — G5
 * Polls the ECS task state and resolves the server's public IP once running.
 */

const { ECSClient, DescribeTasksCommand } = require('@aws-sdk/client-ecs');
const { EC2Client, DescribeNetworkInterfacesCommand } = require('@aws-sdk/client-ec2');
const { DynamoDBClient, GetItemCommand } = require('@aws-sdk/client-dynamodb');

const ecs = new ECSClient({ region: process.env.AWS_REGION });
const ec2 = new EC2Client({ region: process.env.AWS_REGION });
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION });

const SERVER_PORT = 7777;

exports.handler = async (event) => {
    const ticketId = event.pathParameters?.ticketId;
    if (!ticketId) {
        return {
            statusCode: 400,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'INVALID_REQUEST', message: 'ticketId is required' })
        };
    }

    try {
        const dbResponse = await dynamodb.send(new GetItemCommand({
            TableName: process.env.MATCHMAKING_TICKETS_TABLE,
            Key: { ticketId: { S: ticketId } }
        }));

        if (!dbResponse.Item) {
            return {
                statusCode: 404,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'TICKET_NOT_FOUND', message: `Ticket ${ticketId} not found` })
            };
        }

        const taskArn = dbResponse.Item.taskArn.S;
        const playerId = dbResponse.Item.playerId?.S || 'unknown';

        const taskResponse = await ecs.send(new DescribeTasksCommand({
            cluster: process.env.ECS_CLUSTER_ARN,
            tasks: [taskArn]
        }));

        if (!taskResponse.tasks || taskResponse.tasks.length === 0) {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'FAILED', statusReason: 'Task not found in cluster' })
            };
        }

        const task = taskResponse.tasks[0];
        const lastStatus = task.lastStatus;

        console.log(JSON.stringify({ level: 'INFO', ticketId, taskArn, lastStatus }));

        if (['DEPROVISIONING', 'STOPPING', 'STOPPED', 'DELETED'].includes(lastStatus)) {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'FAILED', statusReason: `Task ended: ${lastStatus}` })
            };
        }

        if (lastStatus !== 'RUNNING') {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'SEARCHING', ecsStatus: lastStatus })
            };
        }

        // Task is RUNNING — resolve public IP from ENI
        const eniAttachment = task.attachments?.find(a => a.type === 'ElasticNetworkInterface');
        if (!eniAttachment) {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'SEARCHING', statusReason: 'ENI not yet attached' })
            };
        }

        const eniIdDetail = eniAttachment.details?.find(d => d.name === 'networkInterfaceId');
        if (!eniIdDetail) {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'SEARCHING', statusReason: 'ENI ID not yet available' })
            };
        }

        const eniResponse = await ec2.send(new DescribeNetworkInterfacesCommand({
            NetworkInterfaceIds: [eniIdDetail.value]
        }));

        const publicIp = eniResponse.NetworkInterfaces?.[0]?.Association?.PublicIp;
        if (!publicIp) {
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'SEARCHING', statusReason: 'Public IP not yet assigned' })
            };
        }

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticketId,
                status: 'COMPLETED',
                gameSessionConnectionInfo: {
                    ipAddress: publicIp,
                    port: SERVER_PORT,
                    matchedPlayerSessions: [{ playerId, playerSessionId: taskArn }]
                }
            })
        };
    } catch (error) {
        console.error(JSON.stringify({ level: 'ERROR', message: error.message, stack: error.stack }));
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'STATUS_FETCH_FAILED', message: error.message })
        };
    }
};
