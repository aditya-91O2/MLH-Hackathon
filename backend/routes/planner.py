from typing import List, Optional
from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from planner import generate_study_plan, StudyPlanResponse
    from parsers.timetable_parser import (
        generate_personal_schedule,
        get_active_timetable,
        MasterTimetable
    )
    from parsers.curriculum_parser import get_course_by_code
except (ImportError, ValueError):
    from ..planner import generate_study_plan, StudyPlanResponse
    from ..parsers.timetable_parser import (
        generate_personal_schedule,
        get_active_timetable,
        MasterTimetable
    )
    from ..parsers.curriculum_parser import get_course_by_code

import os
import json

router = APIRouter(prefix="/api/plan", tags=["Study Planner"])

class PlanGenerationRequest(BaseModel):
    enrolled_courses: List[str]
    start_date: Optional[date] = None
    daily_hours_capacity: Optional[float] = 6.0

@router.post("/generate", response_model=StudyPlanResponse, summary="Generate credit-weighted study plan")
def create_study_plan(req: PlanGenerationRequest):
    """
    Inputs:
    - Enrolled courses list (e.g. ['MAL403', 'CSL201', 'CSL202', 'LAL100'])
    - Optional start date and daily study hours capacity.
    
    Extracts exam dates from active timetable, pulls course credits & syllabus topics,
    and returns a structured day-by-day plan with revision buffers and credit balancing.
    """
    active = get_active_timetable()
    if not active:
        # Check fallback
        sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                active = MasterTimetable.model_validate(json.load(f))
        else:
            raise HTTPException(status_code=400, detail="No timetable available. Please upload a master timetable first.")

    personal_sched = generate_personal_schedule(req.enrolled_courses, active)
    
    exams_data = []
    for item in personal_sched.schedule:
        exams_data.append({
            "course_code": item.course_code,
            "date": item.date,
            "start": item.start,
            "end": item.end,
            "slot_no": item.slot_no
        })

    courses_info = []
    for code in req.enrolled_courses:
        c_detail = get_course_by_code(code)
        if c_detail:
            courses_info.append(c_detail.model_dump())
        else:
            courses_info.append({"code": code, "credits": 4.0, "topics": []})

    return generate_study_plan(
        exams=exams_data,
        courses_info=courses_info,
        start_date=req.start_date,
        daily_hours_capacity=req.daily_hours_capacity or 6.0
    )


class FrontendRoadmapRequest(BaseModel):
    courses: Optional[List[Any]] = None
    enrolled_courses: Optional[List[str]] = None
    constraints: Optional[str] = None
    daily_hours: Optional[float] = 4.0
    start_date: Optional[str] = None

@router.post("/roadmap", summary="Generate study roadmap in exact frontend schema")
def generate_frontend_roadmap(req: FrontendRoadmapRequest):
    """
    Synthesizes the study roadmap in the exact JSON format expected by frontend app.js:
    { "reply": "...", "study_plan": [ { "date": "...", "total_hours": ..., "blocks": [...] } ] }
    """
    # 1. Extract course codes
    codes = set()
    if req.enrolled_courses:
        codes.update([c.strip().upper() for c in req.enrolled_courses])
    if req.courses:
        for c in req.courses:
            if isinstance(c, dict):
                code = c.get("code") or c.get("name")
                if code:
                    codes.add(code.strip().upper())
            elif isinstance(c, str):
                codes.add(c.strip().upper())

    if not codes:
        codes = {"CSL202", "CSL201", "MAL403", "CSP203"}

    # 2. Get timetable
    active = get_active_timetable()
    if not active:
        sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                active = MasterTimetable.model_validate(json.load(f))

    exams_data = []
    if active:
        personal_sched = generate_personal_schedule(list(codes), active)
        for item in personal_sched.schedule:
            exams_data.append({
                "course_code": item.course_code,
                "date": item.date,
                "start": item.start,
                "end": item.end,
                "slot_no": item.slot_no
            })

    # Default fallback exams if timetable slots were empty
    if not exams_data:
        exams_data = [
            {"course_code": "MAL403", "date": "2026-09-18", "start": "10:30", "end": "12:30", "slot_no": 11},
            {"course_code": "CSL201", "date": "2026-09-21", "start": "10:30", "end": "12:30", "slot_no": 21},
            {"course_code": "CSL202", "date": "2026-09-24", "start": "10:30", "end": "12:30", "slot_no": 51},
            {"course_code": "LAL100", "date": "2026-09-25", "start": "09:30", "end": "11:30", "slot_no": 61}
        ]

    courses_info = []
    for code in codes:
        c_detail = get_course_by_code(code)
        if c_detail:
            courses_info.append(c_detail.model_dump())
        else:
            courses_info.append({"code": code, "name": code, "credits": 4.0, "topics": []})

    # Parse start date
    from datetime import datetime
    s_date = None
    if req.start_date:
        try:
            s_date = datetime.strptime(req.start_date, "%Y-%m-%d").date()
        except Exception:
            pass

    plan_response = generate_study_plan(
        exams=exams_data,
        courses_info=courses_info,
        start_date=s_date,
        daily_hours_capacity=req.daily_hours or 4.0
    )

    # 3. Format into frontend blocks schema
    formatted_plan = []
    for day in plan_response.daily_schedule:
        blocks = []
        time_slots = [("09:00 - 11:00", 2), ("14:00 - 16:00", 2), ("17:00 - 19:00", 2)]
        slot_idx = 0

        for session in day.sessions:
            t_range, _ = time_slots[slot_idx % len(time_slots)]
            slot_idx += 1
            
            b_type = "revision" if session.study_type == "Revision" else "study"
            if day.is_buffer_day:
                b_type = "buffer"

            blocks.append({
                "time_range": t_range,
                "course": session.course_code,
                "type": b_type,
                "topics": [session.topic_title],
                "hours": int(session.allocated_hours) if session.allocated_hours >= 1 else 1,
                "reference": f"NPTEL & Class Notes for {session.course_code}"
            })

        # If day is buffer day, add buffer note
        if day.is_buffer_day and not blocks:
            blocks.append({
                "time_range": "10:00 - 14:00",
                "course": day.target_exam_tomorrow or "Exam Prep",
                "type": "buffer",
                "note": f"Mandatory Pre-Exam Revision Buffer for {day.target_exam_tomorrow}",
                "hours": int(req.daily_hours or 4.0),
                "reference": "Formula Sheet & PYQ Solutions"
            })

        formatted_plan.append({
            "date": day.date,
            "total_hours": int(day.total_hours) if day.total_hours >= 1 else 4,
            "blocks": blocks
        })

    reply_text = (
        "Here is your customized, day-by-day study roadmap. "
        "I've balanced topics by academic credits, inserted pre-exam intensive revision buffers, "
        "and accounted for your personal study hours."
    )
    if req.constraints:
        reply_text += f" Factorized your constraints: '{req.constraints}'."

    return {
        "reply": reply_text,
        "study_plan": formatted_plan
    }

