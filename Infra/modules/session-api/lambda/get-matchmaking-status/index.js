/**
 * Get Matchmaking Status Lambda Function
 * Retrieves the status of a FlexMatch matchmaking ticket
 */

const { GameLiftClient, DescribeMatchmakingCommand } = require('@aws-sdk/client-gamelift');

const gamelift = new GameLiftClient({ region: process.env.AWS_REGION });
const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

function log(level, message, data = {}) {
    if (LOG_LEVEL === 'DEBUG' || level !== 'DEBUG') {
        console.log(JSON.stringify({ level, message, ...data, timestamp: new Date().toISOString() }));
    }
}

exports.handler = async (event) => {
    log('INFO', 'Get matchmaking status request received', { event });

    try {
        // Extract ticket ID from path parameters
        const ticketId = event.pathParameters?.ticketId;

        if (!ticketId) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    error: 'INVALID_REQUEST',
                    message: 'ticketId is required'
                })
            };
        }

        log('DEBUG', 'Fetching matchmaking status', { ticketId });

        // Describe matchmaking ticket
        const command = new DescribeMatchmakingCommand({
            TicketIds: [ticketId]
        });

        const response = await gamelift.send(command);

        if (!response.TicketList || response.TicketList.length === 0) {
            return {
                statusCode: 404,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    error: 'TICKET_NOT_FOUND',
                    message: `Matchmaking ticket ${ticketId} not found`
                })
            };
        }

        const ticket = response.TicketList[0];

        log('INFO', 'Matchmaking status retrieved', {
            ticketId,
            status: ticket.Status
        });

        // Build response based on ticket status
        const responseBody = {
            ticketId: ticket.TicketId,
            status: ticket.Status,
            statusReason: ticket.StatusReason,
            statusMessage: ticket.StatusMessage,
            startTime: ticket.StartTime,
            endTime: ticket.EndTime,
            estimatedWaitTime: ticket.EstimatedWaitTime
        };

        // Include game session connection info if match is complete
        if (ticket.Status === 'COMPLETED' && ticket.GameSessionConnectionInfo) {
            responseBody.gameSessionConnectionInfo = {
                gameSessionArn: ticket.GameSessionConnectionInfo.GameSessionArn,
                ipAddress: ticket.GameSessionConnectionInfo.IpAddress,
                port: ticket.GameSessionConnectionInfo.Port,
                matchedPlayerSessions: ticket.GameSessionConnectionInfo.MatchedPlayerSessions
            };
        }

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(responseBody)
        };
    } catch (error) {
        log('ERROR', 'Failed to get matchmaking status', {
            error: error.message,
            stack: error.stack
        });

        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                error: 'STATUS_FETCH_FAILED',
                message: error.message
            })
        };
    }
};
