from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Campus Exam Preparation Agent API",
    description="Personalized study planner, timetable parser, and RAG agent powered by Gemma 4",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routes.timetable import router as timetable_router
from routes.courses import router as courses_router
from routes.planner import router as planner_router

# Include API Routers
app.include_router(timetable_router)
app.include_router(courses_router)
app.include_router(planner_router)



@app.get("/")
def read_root():
    return {
        "name": "Campus Exam Preparation Agent API",
        "status": "online",
        "docs_url": "/docs",
        "features": [
            "Dynamic Exam Timetable PDF Upload & Parsing",
            "Personalized Exam Scheduling & Clash Detection",
            "Course Curriculum & Topic Scope Management",
            "Gemma 4 Study Planner & RAG Copilot"
        ]
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "model": "gemma-4"}

