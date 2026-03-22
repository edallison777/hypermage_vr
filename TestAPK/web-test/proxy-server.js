/**
 * CORS proxy + static server for Hypermage VR web test.
 * Serves index.html and proxies /api/* → API Gateway (adds CORS headers).
 */
const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');

const PORT     = 8080;
const API_BASE = 'https://fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com/dev';
const HTML     = path.join(__dirname, 'index.html');

const CORS_HEADERS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

const server = http.createServer((req, res) => {
    const ts = new Date().toISOString().substring(11, 23);

    // Preflight
    if (req.method === 'OPTIONS') {
        res.writeHead(204, CORS_HEADERS);
        res.end();
        return;
    }

    // Serve HTML at root
    if (req.url === '/' || req.url === '/index.html') {
        console.log(`[${ts}] GET  / → index.html`);
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', ...CORS_HEADERS });
        res.end(fs.readFileSync(HTML));
        return;
    }

    // Proxy everything else to API Gateway
    const targetPath = req.url; // e.g. /matchmaking/start
    const chunks     = [];

    req.on('data', c => chunks.push(c));
    req.on('end', () => {
        const body = Buffer.concat(chunks);
        const fwdHeaders = {
            'Content-Type':  req.headers['content-type']  || 'application/json',
            'Content-Length': body.length,
        };
        if (req.headers['authorization']) {
            fwdHeaders['Authorization'] = req.headers['authorization'];
        }

        console.log(`[${ts}] ${req.method} ${targetPath} → API Gateway`);

        const options = {
            hostname: 'fhjoxyk9x5.execute-api.eu-west-1.amazonaws.com',
            path:     `/dev${targetPath}`,
            method:   req.method,
            headers:  fwdHeaders,
        };

        const proxy = https.request(options, proxyRes => {
            const respChunks = [];
            proxyRes.on('data', c => respChunks.push(c));
            proxyRes.on('end', () => {
                const respBody = Buffer.concat(respChunks);
                console.log(`[${ts}] ← ${proxyRes.statusCode} (${respBody.length}b)`);
                res.writeHead(proxyRes.statusCode, {
                    'Content-Type': proxyRes.headers['content-type'] || 'application/json',
                    ...CORS_HEADERS,
                });
                res.end(respBody);
            });
        });

        proxy.on('error', err => {
            console.error(`[${ts}] Proxy error:`, err.message);
            res.writeHead(502, CORS_HEADERS);
            res.end(JSON.stringify({ error: err.message }));
        });

        proxy.write(body);
        proxy.end();
    });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`Hypermage VR proxy server running at http://0.0.0.0:${PORT}`);
    console.log(`Quest browser → http://192.168.178.76:${PORT}`);
});
