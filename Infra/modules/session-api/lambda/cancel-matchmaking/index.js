/**
 * Cancel Matchmaking Lambda — G5
 * Stops the ECS task associated with a matchmaking ticket.
 */

const { ECSClient, StopTaskCommand } = require('@aws-sdk/client-ecs');
const { DynamoDBClient, GetItemCommand, UpdateItemCommand } = require('@aws-sdk/client-dynamodb');

const ecs = new ECSClient({ region: process.env.AWS_REGION });
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION });

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
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'CANCELLED', note: 'Ticket not found' })
            };
        }

        const taskArn = dbResponse.Item.taskArn.S;

        try {
            await ecs.send(new StopTaskCommand({
                cluster: process.env.ECS_CLUSTER_ARN,
                task: taskArn,
                reason: 'UserCancelled'
            }));
        } catch (ecsErr) {
            console.log(JSON.stringify({ level: 'WARN', message: 'StopTask skipped (task already stopped)', error: ecsErr.message }));
        }

        await dynamodb.send(new UpdateItemCommand({
            TableName: process.env.MATCHMAKING_TICKETS_TABLE,
            Key: { ticketId: { S: ticketId } },
            UpdateExpression: 'SET #s = :cancelled',
            ExpressionAttributeNames: { '#s': 'status' },
            ExpressionAttributeValues: { ':cancelled': { S: 'CANCELLED' } }
        }));

        console.log(JSON.stringify({ level: 'INFO', message: 'Matchmaking cancelled', ticketId, taskArn }));

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticketId, status: 'CANCELLED' })
        };
    } catch (error) {
        console.error(JSON.stringify({ level: 'ERROR', message: error.message, stack: error.stack }));
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'CANCEL_FAILED', message: error.message })
        };
    }
};
