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
    const req = {
        method: 'POST',
        body: {
            messages: [
                { role: "user", content: "Hi! I have exams coming up." },
                { role: "assistant", content: "Hello! I can help you create a personalized study plan. To get started, you can tell me about your exams, upload your timetable, or let me know how many hours you can study each day." },
                { role: "user", content: "My physics exam is on Dec 1st. I can study 4 hours a day." }
            ],
            context: {
                courses: [],
                study_hours: null,
                start_date: null
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
    
    console.log("Testing conversation...");
    await handler(req, res);
    console.log("Status:", statusCode);
    console.log("Result:", JSON.stringify(jsonResult, null, 2));
}

runTest();
