/**
 * GET /leaderboard?limit=N — Cognito-authed. Returns the top-N high scores
 * (descending) from the PlayerScores LeaderboardIndex GSI. Read-only; 72h TTL on
 * the table means stale entries fall off automatically (F6b — see FEATURE_PLAN.md).
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, QueryCommand } = require('@aws-sdk/lib-dynamodb');

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
        const qs    = (event && event.queryStringParameters) || {};
        let limit   = parseInt(qs.limit, 10);
        if (!Number.isFinite(limit) || limit <= 0) limit = 10;
        limit = Math.min(limit, 100);

        const res = await dynamodb.send(new QueryCommand({
            TableName: PLAYER_SCORES_TABLE,
            IndexName: 'LeaderboardIndex',
            KeyConditionExpression: 'leaderboardId = :lid',
            ExpressionAttributeValues: { ':lid': 'global' },
            ScanIndexForward: false,   // highest totalScore first
            Limit: limit,
        }));

        const entries = (res.Items || []).map((it, i) => ({
            rank:        i + 1,
            playerId:    it.playerId,
            displayName: it.displayName || it.playerId,
            score:       it.totalScore,
        }));

        log('INFO', 'Leaderboard read', { count: entries.length, limit });
        return { statusCode: 200, headers: CORS, body: JSON.stringify({ leaderboard: entries }) };

    } catch (err) {
        log('ERROR', 'Leaderboard query failed', { error: err.message });
        return { statusCode: 500, headers: CORS, body: JSON.stringify({ error: 'QUERY_FAILED', message: err.message }) };
    }
};
