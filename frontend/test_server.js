const http = require('http');
const fs = require('fs');
const path = require('path');

// Load env
try {
    const envLocal = fs.readFileSync('.env.local', 'utf8');
    envLocal.split('\n').forEach(line => {
        const [key, ...vals] = line.split('=');
        if (key && vals.length) {
            process.env[key.trim()] = vals.join('=').trim();
        }
    });
} catch (e) {}

const server = http.createServer(async (req, res) => {
    if (req.url === '/api/gemma' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', async () => {
            try {
                req.body = JSON.parse(body);
                const expressRes = {
                    status: function(code) { this.statusCode = code; return this; },
                    json: function(data) {
                        res.writeHead(this.statusCode || 200, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify(data));
                    }
                };
                const handler = (await import('./api/gemma.js')).default;
                await handler(req, expressRes);
            } catch (e) {
                console.error(e);
                res.writeHead(500);
                res.end('Server Error');
            }
        });
        return;
    }

    // Serve static files
    let filePath = '.' + req.url;
    if (filePath === './') filePath = './index.html';
    const extname = path.extname(filePath);
    let contentType = 'text/html';
    switch (extname) {
        case '.js': contentType = 'text/javascript'; break;
        case '.css': contentType = 'text/css'; break;
    }
    fs.readFile(filePath, (error, content) => {
        if (error) {
            res.writeHead(404);
            res.end('Not found');
        } else {
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content, 'utf-8');
        }
    });
});

server.listen(3000, () => {
    console.log('Test server running at http://localhost:3000/');
});
