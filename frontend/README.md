# Study Planner

A lightweight, AI-powered study planner website that helps students generate a day-wise study plan based on their exam timetable and study resources.

## Project Objective
The goal is to allow students to upload or paste their exam timetable, input course credits, and provide study materials (notes, WhatsApp exports, etc.). The system will eventually use Google's Gemini API to extract courses, analyze topics, and formulate a customized daily study schedule.

## Technology Stack
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend (Future Phase)**: Node.js (Vercel Serverless Functions)
- **AI (Future Phase)**: Google Gemini API

## File Structure
```text
study-planner/
├── index.html        # Main application UI
├── style.css         # Styling and layout (Responsive, Custom CSS)
├── app.js            # Frontend logic and DOM manipulation
├── api/
│   └── gemma.js      # Placeholder for Vercel serverless function
├── .gitignore
└── README.md         # Project documentation
```

## Current Functionality (Phase 1)
- **UI Foundation**: A clean, single-page responsive academic dashboard layout.
- **Timetable Section**: Inputs for images and text, with a dynamic table for manually adding, editing, and deleting courses.
- **Resources Section**: Textarea for pasting notes and file input capable of reading `.txt` files directly into the browser.
- **Study Plan Section**: Date and hour inputs, along with native browser printing functionality.

## Deferred to Later Phases
- Integration with the Gemini API.
- Automatic extraction of courses from uploaded images or pasted text.
- AI analysis of topics from study resources.
- Automated generation of the daily study plan.
- Server-side validation and rate limiting.

## Local Development Instructions
To run this project locally, simply serve the files using any static file server. For example, using Python 3:
```bash
cd study-planner
python -m http.server 8000
```
Then open `http://localhost:8000` in your web browser.
