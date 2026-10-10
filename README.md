# 🎓 Personalized Campus Exam Preparation Agent (Backend API)
> **Theme:** Build for Your Campus | **MLH Tracks:** Best Use of Gemma 4, Best Open Source AI Project

An intelligent academic companion backend that transforms raw university master timetables and multi-page course curricula into personalized exam timetables, credit-weighted study roadmaps, curated NPTEL learning resources, and grounded doubt-clearing assistance.

---

## 🌟 Why Gemma 4?
Gemma 4 serves as the core intelligence engine across the agent workflow:
1. **Strict JSON Schema Extraction**: Transforms complex, interleaved timetable PDFs and multi-page curriculum tables into structured JSON with Pydantic validation.
2. **Topic Decomposition & Complexity Estimation**: Deconstructs raw syllabus paragraphs into coherent subtopics, assigning difficulty weights and estimated study hours.
3. **Constraint-Aware Study Planning**: Reasons over exam dates, course credits (e.g., 4-credit theory vs 2-credit labs), and topic sizes to generate balanced day-by-day study schedules.
4. **Grounded Course Chatbot (RAG)**: Provides accurate academic answers citing specific course syllabus modules, rejecting hallucinated material.
5. **Tool Calling & Agentic Search**: Executes tools (`search_youtube(prefer="NPTEL")`, `get_exam_schedule`) to supplement missing classroom topics.

> **Deterministic vs LLM Division of Responsibility**: Date arithmetic, clash detection, and credit baseline weightings are handled deterministically in Python, while Gemma 4 focuses on natural language parsing, pedagogical reasoning, and contextual explanations.

---

## 🏗️ Repository Structure
```
MLH-Hackathon/
├── backend/                  # Python FastAPI Backend
│   ├── parsers/              # Timetable & Curriculum extractors
│   ├── routes/               # API endpoints
│   ├── llm.py                # Gemma 4 wrapper (JSON schema + retry logic)
│   ├── planner.py            # Study plan generation logic
│   ├── rag.py                # Retrieval-Augmented Generation chatbot
│   ├── main.py               # FastAPI entry point
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Environment variables template
├── data/                     # timetable.json, courses.json
├── docs/                     # slides.pptx, architecture diagram
├── SKILL.md                  # Agent Skill Specification
├── README.md                 # Project Documentation
└── LICENSE                   # MIT License
```

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.10+
- Gemma 4 API Key

### Backend Setup
```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Interactive API Documentation
Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 👥 Authors & License
Licensed under the [MIT License](LICENSE). Built for the MLH Hackathon.
