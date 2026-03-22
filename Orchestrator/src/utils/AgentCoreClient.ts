/**
 * Bedrock AgentCore Runtime Client
 *
 * Makes SigV4-signed HTTPS requests to the Bedrock AgentCore runtime.
 * Parses Server-Sent Events (SSE) streaming responses into a single string.
 */

import * as https from 'node:https';
import * as crypto from 'node:crypto';
import { defaultProvider } from '@aws-sdk/credential-provider-node';

const REGION = 'eu-west-1';
const SERVICE = 'bedrock-agentcore';
const HOSTNAME = `${SERVICE}.${REGION}.amazonaws.com`;

// ── Minimal SigV4 implementation using node:crypto ──────────────────────────

function sha256Hex(data: string | Buffer): string {
    return crypto.createHash('sha256').update(data).digest('hex');
}

function hmacSha256(key: Buffer, data: string): Buffer {
    return crypto.createHmac('sha256', key).update(data).digest();
}

function signingKey(secret: string, date: string, region: string, service: string): Buffer {
    const kDate = hmacSha256(Buffer.from(`AWS4${secret}`, 'utf8'), date);
    const kRegion = hmacSha256(kDate, region);
    const kService = hmacSha256(kRegion, service);
    return hmacSha256(kService, 'aws4_request');
}

interface SignedHeaders {
    [key: string]: string;
}

async function signRequest(
    method: string,
    path: string,
    body: string
): Promise<SignedHeaders> {
    const creds = await defaultProvider()();
    const now = new Date();
    const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '').slice(0, 15) + 'Z'; // 20260322T120000Z
    const dateStamp = amzDate.slice(0, 8); // 20260322

    const payloadHash = sha256Hex(Buffer.from(body, 'utf8'));
    const credentialScope = `${dateStamp}/${REGION}/${SERVICE}/aws4_request`;

    const canonicalHeaders =
        `content-type:application/json\n` +
        `host:${HOSTNAME}\n` +
        `x-amz-content-sha256:${payloadHash}\n` +
        `x-amz-date:${amzDate}\n`;

    const signedHeadersList = 'content-type;host;x-amz-content-sha256;x-amz-date';

    // Append session token header if present
    const sessionToken = creds.sessionToken;
    const canonicalHeadersFull = sessionToken
        ? canonicalHeaders + `x-amz-security-token:${sessionToken}\n`
        : canonicalHeaders;
    const signedHeadersFull = sessionToken
        ? signedHeadersList + ';x-amz-security-token'
        : signedHeadersList;

    const canonicalRequest = [
        method,
        path,
        '', // no query string
        canonicalHeadersFull,
        signedHeadersFull,
        payloadHash,
    ].join('\n');

    const stringToSign = [
        'AWS4-HMAC-SHA256',
        amzDate,
        credentialScope,
        sha256Hex(Buffer.from(canonicalRequest, 'utf8')),
    ].join('\n');

    const key = signingKey(creds.secretAccessKey, dateStamp, REGION, SERVICE);
    const signature = crypto.createHmac('sha256', key).update(stringToSign).digest('hex');

    const headers: SignedHeaders = {
        'Content-Type': 'application/json',
        'x-amz-date': amzDate,
        'x-amz-content-sha256': payloadHash,
        Authorization:
            `AWS4-HMAC-SHA256 Credential=${creds.accessKeyId}/${credentialScope}, ` +
            `SignedHeaders=${signedHeadersFull}, ` +
            `Signature=${signature}`,
    };

    if (sessionToken) {
        headers['x-amz-security-token'] = sessionToken;
    }

    return headers;
}

// ── SSE parser ────────────────────────────────────────────────────────────────

function parseSseBody(raw: string): string {
    // SSE lines look like:  data: "chunk of text"
    // Collect all data lines and join them
    return raw
        .split('\n')
        .filter((line) => line.startsWith('data: '))
        .map((line) => {
            const value = line.slice(6).trim();
            // Strip surrounding JSON quotes if present (e.g. data: "hello" → hello)
            if (value.startsWith('"') && value.endsWith('"')) {
                try {
                    return JSON.parse(value) as string;
                } catch {
                    return value;
                }
            }
            return value;
        })
        .join('');
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Invoke a deployed Bedrock AgentCore runtime.
 *
 * @param agentArn  Full ARN from deployment_results.json
 * @param prompt    Natural-language instruction for the agent
 * @param correlationId  Forwarded through x-amzn-requestid for tracing
 * @returns Concatenated text response from the agent
 */
export async function invokeAgent(
    agentArn: string,
    prompt: string,
    correlationId: string
): Promise<string> {
    // Extract the runtime ID from the ARN
    // e.g. arn:aws:bedrock-agentcore:eu-west-1:732231126129:runtime/AssetPipeline_Agent-siqbOWHci2
    const runtimeId = agentArn.split('/').pop();
    if (!runtimeId) {
        throw new Error(`Cannot extract runtime ID from ARN: ${agentArn}`);
    }

    const path = `/runtimes/${runtimeId}/invocations`;
    const body = JSON.stringify({ prompt });
    const headers = await signRequest('POST', path, body);
    headers['x-amzn-requestid'] = correlationId;
    headers['Content-Length'] = String(Buffer.byteLength(body, 'utf8'));

    return new Promise<string>((resolve, reject) => {
        const req = https.request(
            {
                hostname: HOSTNAME,
                path,
                method: 'POST',
                headers,
            },
            (res) => {
                const chunks: Buffer[] = [];
                res.on('data', (chunk: Buffer) => chunks.push(chunk));
                res.on('end', () => {
                    if (res.statusCode && res.statusCode >= 400) {
                        const body = Buffer.concat(chunks).toString('utf8');
                        reject(
                            new Error(
                                `AgentCore HTTP ${res.statusCode} for ${runtimeId}: ${body}`
                            )
                        );
                        return;
                    }
                    const raw = Buffer.concat(chunks).toString('utf8');
                    resolve(parseSseBody(raw));
                });
                res.on('error', reject);
            }
        );
        req.on('error', reject);
        req.write(body);
        req.end();
    });
}
