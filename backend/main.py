import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from routes.chat import router as chat_router
from routes.materials import router as materials_router

# Include API Routers
app.include_router(timetable_router)
app.include_router(courses_router)
app.include_router(planner_router)
app.include_router(chat_router)
app.include_router(materials_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "model": "gemma-4"}

# Mount frontend directory for full-stack unified serving
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
