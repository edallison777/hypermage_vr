/**
 * Cancel Matchmaking Lambda Function
 * Stops an active FlexMatch matchmaking ticket.
 */

const { GameLiftClient, StopMatchmakingCommand } = require('@aws-sdk/client-gamelift');

const gamelift = new GameLiftClient({ region: process.env.AWS_REGION });
const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

function log(level, message, data = {}) {
    if (LOG_LEVEL === 'DEBUG' || level !== 'DEBUG') {
        console.log(JSON.stringify({ level, message, ...data, timestamp: new Date().toISOString() }));
    }
}

exports.handler = async (event) => {
    const ticketId = event.pathParameters?.ticketId;

    if (!ticketId) {
        return {
            statusCode: 400,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'INVALID_REQUEST', message: 'ticketId is required' })
        };
    }

    log('INFO', 'Cancel matchmaking request', { ticketId });

    try {
        const command = new StopMatchmakingCommand({ TicketId: ticketId });
        await gamelift.send(command);

        log('INFO', 'Matchmaking cancelled', { ticketId });
        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticketId, status: 'CANCELLED' })
        };
    } catch (error) {
        // NotFoundException or InvalidRequestException both mean the ticket is already gone —
        // treat as idempotent success: the matchmaking is definitely not proceeding.
        const errorName = error.name || error.__type || '';
        if (errorName.includes('NotFoundException') || errorName.includes('InvalidRequest')) {
            log('WARN', 'Ticket not found or already ended — treating as cancelled', { ticketId, error: error.message });
            return {
                statusCode: 200,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticketId, status: 'CANCELLED', note: 'Ticket already ended' })
            };
        }

        log('ERROR', 'Failed to cancel matchmaking', { ticketId, error: error.message, stack: error.stack });
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'CANCEL_FAILED', message: error.message })
        };
    }
};
