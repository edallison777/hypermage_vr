/**
 * Post Session Summary Lambda Function
 * Stores player session summary with rewards in DynamoDB
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand, UpdateCommand } = require('@aws-sdk/lib-dynamodb');

const client = new DynamoDBClient({ region: process.env.AWS_REGION });
const dynamodb = DynamoDBDocumentClient.from(client);

const PLAYER_SESSIONS_TABLE = process.env.PLAYER_SESSIONS_TABLE;
const PLAYER_REWARDS_TABLE = process.env.PLAYER_REWARDS_TABLE;
const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

function log(level, message, data = {}) {
    if (LOG_LEVEL === 'DEBUG' || level !== 'DEBUG') {
        console.log(JSON.stringify({ level, message, ...data, timestamp: new Date().toISOString() }));
    }
}

exports.handler = async (event) => {
    log('INFO', 'Post session summary request received', { event });

    try {
        // Parse request body
        const body = JSON.parse(event.body || '{}');
        const { playerId, sessionId, rewards = [], endTime } = body;

        // Validate required fields
        if (!playerId || !sessionId) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    error: 'INVALID_REQUEST',
                    message: 'playerId and sessionId are required'
                })
            };
        }

        log('DEBUG', 'Processing session summary', { playerId, sessionId, rewardCount: rewards.length });

        const now = new Date().toISOString();
        const sessionEndTime = endTime || now;

        // Calculate TTL: 72 hours (259200 seconds) after session end
        const ttl = Math.floor(new Date(sessionEndTime).getTime() / 1000) + 259200;

        // Store session summary with TTL
        if (PLAYER_SESSIONS_TABLE) {
            const sessionCommand = new PutCommand({
                TableName: PLAYER_SESSIONS_TABLE,
                Item: {
                    playerId,
                    sessionId,
                    endTime: sessionEndTime,
                    rewards,
                    ttl, // DynamoDB will auto-delete after 72 hours
                    createdAt: now
                }
            });

            await dynamodb.send(sessionCommand);
            log('DEBUG', 'Session summary stored', { playerId, sessionId, ttl });
        }

        // Store rewards as persistent boolean flags (no TTL)
        if (PLAYER_REWARDS_TABLE && rewards.length > 0) {
            for (const rewardId of rewards) {
                const rewardCommand = new UpdateCommand({
                    TableName: PLAYER_REWARDS_TABLE,
                    Key: {
                        playerId,
                        rewardId
                    },
                    UpdateExpression: 'SET granted = :true, grantedAt = :now, sessionId = :sessionId',
                    ExpressionAttributeValues: {
                        ':true': true,
                        ':now': now,
                        ':sessionId': sessionId
                    }
                });

                await dynamodb.send(rewardCommand);
            }

            log('INFO', 'Rewards stored successfully', {
                playerId,
                sessionId,
                rewardCount: rewards.length
            });
        }

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                success: true,
                playerId,
                sessionId,
                rewardsStored: rewards.length,
                ttl
            })
        };
    } catch (error) {
        log('ERROR', 'Failed to store session summary', {
            error: error.message,
            stack: error.stack
        });

        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                error: 'STORAGE_FAILED',
                message: error.message
            })
        };
    }
};
