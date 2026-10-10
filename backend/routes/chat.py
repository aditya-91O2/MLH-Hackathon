"""
POST /api/chat — RAG chatbot endpoint.
Receives: course_code, message, history, user_id, optional context.
Returns: answer, citations, intent, video_recommendations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from ..rag import query_rag, normalize_course_code

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    course_code: str = Field(..., description="e.g. 'CSL202' or 'csl-202' or 'CSL202/MAL504'")
    message: str = Field(..., description="Student's raw question")
    history: list[ChatTurn] = Field(default_factory=list)
    user_id: str = Field(default="default_user", description="Unique student ID for data isolation")
    enrolled_courses: list[str] = Field(default_factory=list, description="All courses student is enrolled in")
    scope_data: Optional[dict] = Field(default=None, description="Topics in/out of scope from Step 3")
    plan_data: Optional[dict] = Field(default=None, description="Study plan from planner.py")
    timetable_data: Optional[dict] = Field(default=None, description="Parsed timetable JSON")


class ChatResponse(BaseModel):
    answer: str
    intent: str
    citations: list[dict]
    video_recommendations: list[dict]
    clarification_needed: bool
    clarification_question: Optional[str]
    normalized_course: str


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip() and not req.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    history_dicts = [{"role": t.role, "content": t.content} for t in req.history]

    result = query_rag(
        course_code=req.course_code,
        user_query=req.message,
        chat_history=history_dicts,
        user_id=req.user_id,
        enrolled_courses=req.enrolled_courses or [req.course_code],
        scope_data=req.scope_data,
        plan_data=req.plan_data,
        timetable_data=req.timetable_data,
    )

    return ChatResponse(
        answer=result["answer"],
        intent=result["intent"],
        citations=result["citations"],
        video_recommendations=result["video_recommendations"],
        clarification_needed=result["clarification_needed"],
        clarification_question=result["clarification_question"],
        normalized_course=normalize_course_code(req.course_code),
    )
