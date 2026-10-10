"""
POST /api/chat — RAG Chatbot powered by Gemma 4 and ChromaDB VectorStore.
Receives: course_code, message, history, user_id, optional context.
Returns: answer, citations, intent, clarification flags.
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

try:
    from rag import query_rag, normalize_course_code
except (ImportError, ValueError):
    from ..rag import query_rag, normalize_course_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    course_code: Optional[str] = Field(default="", description="e.g. 'CSL202'")
    message: str = Field(..., description="Student's prompt")
    history: List[ChatTurn] = Field(default_factory=list)
    user_id: str = Field(default="default_user", description="Unique student ID")
    enrolled_courses: List[str] = Field(default_factory=list)
    scope_data: Optional[Dict[str, Any]] = None
    plan_data: Optional[Dict[str, Any]] = None
    timetable_data: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    answer: str
    reply: Optional[str] = None
    intent: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    video_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    normalized_course: str = ""


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    course = (req.course_code or "").strip().upper().replace("-", "")
    history_dicts = [{"role": t.role, "content": t.content} for t in req.history]

    timetable_payload = req.timetable_data
    if not timetable_payload or (not timetable_payload.get("slots") and not timetable_payload.get("courses")):
        try:
            from parsers.timetable_parser import get_active_timetable
            active_tt = get_active_timetable()
            if active_tt:
                timetable_payload = active_tt.model_dump()
            else:
                import os, json
                sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
                if os.path.exists(sample_path):
                    with open(sample_path, "r", encoding="utf-8") as f:
                        timetable_payload = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to auto-load timetable for chat: {e}")

    plan_payload = req.plan_data
    if not plan_payload or not plan_payload.get("workload_weights"):
        try:
            import os, json
            plan_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "active_plan.json")
            if os.path.exists(plan_path):
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan_payload = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to auto-load plan for chat: {e}")

    rag_result = query_rag(
        course_code=course,
        user_query=req.message,
        chat_history=history_dicts,
        user_id=req.user_id,
        enrolled_courses=req.enrolled_courses,
        scope_data=req.scope_data,
        plan_data=plan_payload,
        timetable_data=timetable_payload,
    )

    answer = rag_result.get("answer", "")
    return ChatResponse(
        answer=answer,
        reply=rag_result.get("reply", answer),
        intent=rag_result.get("intent", "CONCEPT"),
        citations=rag_result.get("citations", []),
        video_recommendations=[],  # Strictly NO video / yt data per user instruction
        clarification_needed=rag_result.get("clarification_needed", False),
        clarification_question=rag_result.get("clarification_question"),
        normalized_course=normalize_course_code(course) if course else "",
    )
