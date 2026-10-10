import fs from 'fs';
import handler from './api/gemma.js';

// Load env
const envLocal = fs.readFileSync('.env.local', 'utf8');
envLocal.split('\n').forEach(line => {
    const [key, ...vals] = line.split('=');
    if (key && vals.length) {
        process.env[key.trim()] = vals.join('=').trim();
    }
});

async function runTest() {
    const imageBase64 = fs.readFileSync('timetable.png').toString('base64');
    
    const req = {
        method: 'POST',
        body: {
            messages: [
                { role: "user", content: "Extract timetable from image." }
            ],
            context: { courses: [] },
            image: {
                mime: "image/png",
                data: imageBase64
            }
        }
    };
    
    let statusCode = 0;
    let jsonResult = null;
    
    const res = {
        status: (code) => {
            statusCode = code;
            return res;
        },
        json: (data) => {
            jsonResult = data;
        }
    };
    
    console.log("Testing image extraction...");
    await handler(req, res);
    console.log("Status:", statusCode);
    console.log("Result:", JSON.stringify(jsonResult, null, 2));
}

runTest();
