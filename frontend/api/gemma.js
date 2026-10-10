/**
 * Vercel Serverless Function (Phase 2A)
 * Conversational endpoint for extracting study planner data using Gemini API.
 */

export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed. Use POST.' });
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
        return res.status(500).json({ error: 'GEMINI_API_KEY is not configured on the server.' });
    }

    const { messages, context, image } = req.body;

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
        return res.status(400).json({ error: 'Messages array is required.' });
    }

    const modelId = 'gemma-4-26b-a4b-it';
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${modelId}:generateContent?key=${apiKey}`;

    try {
        const contents = [];
        
        // Build multi-turn content history
        for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];
            const role = msg.role === 'assistant' ? 'model' : 'user';
            const parts = [{ text: msg.content || " " }];
            
            // Attach image to the latest user message
            if (image && i === messages.length - 1 && role === 'user') {
                if (!image.mime || !image.data) {
                    return res.status(400).json({ error: 'Invalid image format.' });
                }
                parts.unshift({
                    inlineData: {
                        mimeType: image.mime,
                        data: image.data
                    }
                });
            }
            contents.push({ role, parts });
        }

        // If no user message was found but an image is present (edge case)
        if (contents.length === 0 && image) {
            contents.push({
                role: 'user',
                parts: [
                    { inlineData: { mimeType: image.mime, data: image.data } },
                    { text: "Extract info from this image." }
                ]
            });
        }

        const systemText = `You are a helpful, conversational study planner assistant.
Current known context state:
${JSON.stringify(context || {})}

Instructions:
1. Extract any NEW information (courses, exam dates, study hours, start date) from the user's latest input.
2. Formulate a natural, conversational reply acknowledging the input, confirming what was extracted, and asking ONE logical follow-up question. Don't ask for everything at once. Keep the conversation flowing smoothly.
3. Your FINAL output MUST contain a single \`\`\`json code block. Put the JSON inside it. Do NOT output the final JSON without the \`\`\`json wrapper.
4. Do NOT invent missing fields. If study hours or a start date is not explicitly mentioned by the user, omit it from extracted_data.

JSON Schema:
\`\`\`json
{
  "reply": "Your conversational response here.",
  "extracted_data": {
    "courses": [{"name": "Course Name", "exam_date": "2026-12-01"}],
    "study_hours": 4,
    "start_date": "2026-11-01"
  }
}
\`\`\``;

        const payload = {
            contents: contents,
            systemInstruction: { parts: [{ text: systemText }] },
            generationConfig: {
                responseMimeType: 'application/json',
                responseSchema: {
                    type: "OBJECT",
                    properties: {
                        reply: { type: "STRING" },
                        extracted_data: {
                            type: "OBJECT",
                            properties: {
                                courses: {
                                    type: "ARRAY",
                                    items: {
                                        type: "OBJECT",
                                        properties: {
                                            name: { type: "STRING" },
                                            exam_date: { type: "STRING" }
                                        },
                                        required: ["name", "exam_date"]
                                    }
                                },
                                study_hours: { type: "NUMBER" },
                                start_date: { type: "STRING" }
                            }
                        }
                    },
                    required: ["reply"]
                }
            }
        };

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Gemini API Error:', response.status, errorText);
            if (response.status === 404 && errorText.includes('models/')) {
                 return res.status(404).json({ error: `The requested model '${modelId}' was not found or does not support this API endpoint.` });
            }
            return res.status(response.status).json({ error: 'Failed to communicate with AI provider.' });
        }

        const data = await response.json();
        
        if (!data.candidates || data.candidates.length === 0 || !data.candidates[0].content) {
            return res.status(500).json({ error: 'Received an empty response from the AI model.' });
        }

        let resultText = data.candidates[0].content.parts[0].text;
        
        // Robust extraction for noisy "thinking" models
        let jsonStr = resultText;
        const jsonBlockStart = resultText.lastIndexOf('```json');
        if (jsonBlockStart !== -1) {
            jsonStr = resultText.substring(jsonBlockStart + 7).trim();
            if (jsonStr.endsWith('```')) {
                jsonStr = jsonStr.substring(0, jsonStr.length - 3).trim();
            }
        } else {
            // Find the outermost '{' and '}' bounds if no code fences are used
            const start = resultText.indexOf('{');
            const end = resultText.lastIndexOf('}');
            if (start !== -1 && end !== -1 && end > start) {
                jsonStr = resultText.substring(start, end + 1);
            }
        }
        
        jsonStr = jsonStr.trim();

        let parsedJson;
        try {
            parsedJson = JSON.parse(jsonStr);
        } catch (e) {
            console.error("Failed to parse JSON:", jsonStr);
            return res.status(500).json({ error: 'Model generated invalid JSON.' });
        }

        return res.status(200).json(parsedJson);

    } catch (error) {
        console.error('Server error:', error);
        return res.status(500).json({ error: 'Internal server error during AI request.' });
    }
}
