/**
 * POST /scores — Cognito-authed. Upserts player high score.
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, UpdateCommand } = require('@aws-sdk/lib-dynamodb');

const client   = new DynamoDBClient({ region: process.env.AWS_REGION });
const dynamodb = DynamoDBDocumentClient.from(client);
const PLAYER_SCORES_TABLE = process.env.PLAYER_SCORES_TABLE;
const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

const CORS = { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' };

function log(level, message, data = {}) {
    if (LOG_LEVEL === 'DEBUG' || level !== 'DEBUG') {
        console.log(JSON.stringify({ level, message, ...data, timestamp: new Date().toISOString() }));
    }
}

exports.handler = async (event) => {
    try {
        const claims   = (event.requestContext && event.requestContext.authorizer && event.requestContext.authorizer.claims) || {};
        const playerId = claims.sub;
        if (!playerId) {
            return { statusCode: 401, headers: CORS, body: JSON.stringify({ error: 'UNAUTHORIZED' }) };
        }

        const displayName = claims.email || claims['cognito:username'] || claims.preferred_username || playerId;
        const body        = JSON.parse(event.body || '{}');
        const { score, sessionId } = body;

        if (typeof score !== 'number' || score < 0) {
            return { statusCode: 400, headers: CORS, body: JSON.stringify({ error: 'INVALID_REQUEST', message: 'score must be a non-negative number' }) };
        }

        const now = new Date().toISOString();
        // 72h rolling TTL (matches the reward-persistence model) so the board self-trims.
        const ttl = Math.floor(Date.now() / 1000) + 72 * 60 * 60;

        await dynamodb.send(new UpdateCommand({
            TableName: PLAYER_SCORES_TABLE,
            Key: { playerId },
            UpdateExpression: 'SET leaderboardId = :lid, displayName = :dn, ' +
                'gamesPlayed = if_not_exists(gamesPlayed, :zero) + :one, ' +
                'lastUpdated = :now, totalScore = :score, #ttl = :ttl',
            ConditionExpression: 'attribute_not_exists(totalScore) OR totalScore < :score',
            ExpressionAttributeNames: { '#ttl': 'ttl' },
            ExpressionAttributeValues: {
                ':lid':   'global',
                ':dn':    displayName,
                ':score': score,
                ':zero':  0,
                ':one':   1,
                ':now':   now,
                ':ttl':   ttl,
            },
        }));

        log('INFO', 'High score saved', { playerId, score, sessionId });
        return { statusCode: 200, headers: CORS, body: JSON.stringify({ success: true, playerId, score }) };

    } catch (err) {
        if (err.name === 'ConditionalCheckFailedException') {
            return { statusCode: 200, headers: CORS, body: JSON.stringify({ success: true, note: 'not a new high score' }) };
        }
        log('ERROR', 'Score update failed', { error: err.message });
        return { statusCode: 500, headers: CORS, body: JSON.stringify({ error: 'STORAGE_FAILED', message: err.message }) };
    }
};
