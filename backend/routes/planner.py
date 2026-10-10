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
