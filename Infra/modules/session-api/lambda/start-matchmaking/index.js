/**
 * Start Matchmaking Lambda Function
 * Initiates a FlexMatch matchmaking request for a player
 */

const { GameLiftClient, StartMatchmakingCommand } = require('@aws-sdk/client-gamelift');

const gamelift = new GameLiftClient({ region: process.env.AWS_REGION });
const MATCHMAKING_CONFIG_NAME = process.env.MATCHMAKING_CONFIG_NAME;
const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

function log(level, message, data = {}) {
    if (LOG_LEVEL === 'DEBUG' || level !== 'DEBUG') {
        console.log(JSON.stringify({ level, message, ...data, timestamp: new Date().toISOString() }));
    }
}

exports.handler = async (event) => {
    log('INFO', 'Start matchmaking request received', { event });

    try {
        // Parse request body
        const body = JSON.parse(event.body || '{}');
        const { playerId, playerAttributes = {} } = body;

        // Validate required fields
        if (!playerId) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    error: 'INVALID_REQUEST',
                    message: 'playerId is required'
                })
            };
        }

        // Extract player info from Cognito authorizer context
        const cognitoUsername = event.requestContext?.authorizer?.claims?.sub;
        const cognitoEmail = event.requestContext?.authorizer?.claims?.email;

        log('DEBUG', 'Player info extracted', { playerId, cognitoUsername, cognitoEmail });

        // Build player attributes with defaults
        const attributes = {
            skill: playerAttributes.skill || 10,
            region: playerAttributes.region || 'eu-west-1',
            ...playerAttributes
        };

        // Start matchmaking
        const command = new StartMatchmakingCommand({
            ConfigurationName: MATCHMAKING_CONFIG_NAME,
            Players: [
                {
                    PlayerId: playerId,
                    PlayerAttributes: attributes,
                    LatencyInMs: playerAttributes.latencyInMs || {}
                }
            ]
        });

        const response = await gamelift.send(command);

        log('INFO', 'Matchmaking started successfully', {
            ticketId: response.MatchmakingTicket.TicketId,
            playerId
        });

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticketId: response.MatchmakingTicket.TicketId,
                status: response.MatchmakingTicket.Status,
                estimatedWaitTime: response.MatchmakingTicket.EstimatedWaitTime,
                startTime: response.MatchmakingTicket.StartTime
            })
        };
    } catch (error) {
        log('ERROR', 'Failed to start matchmaking', {
            error: error.message,
            stack: error.stack
        });

        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                error: 'MATCHMAKING_FAILED',
                message: error.message
            })
        };
    }
};
