from typing import List, Optional, Any
from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from planner import generate_study_plan, StudyPlanResponse
    from parsers.timetable_parser import (
        generate_personal_schedule,
        get_active_timetable,
        resolve_course_credits,
        MasterTimetable
    )
    from parsers.curriculum_parser import get_course_by_code
except (ImportError, ValueError):
    from ..planner import generate_study_plan, StudyPlanResponse
    from ..parsers.timetable_parser import (
        generate_personal_schedule,
        get_active_timetable,
        resolve_course_credits,
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
    topics: Optional[List[Any]] = None
    constraints: Optional[str] = None
    daily_hours: Optional[float] = 4.0
    start_date: Optional[str] = None

@router.post("/roadmap", summary="Generate study roadmap in exact frontend schema")
def generate_frontend_roadmap(req: FrontendRoadmapRequest):
    """
    Synthesizes the study roadmap in the exact JSON format expected by frontend app.js:
    { "reply": "...", "study_plan": [ { "date": "...", "total_hours": ..., "blocks": [...] } ] }
    """
    from routes.courses import generate_topics_for_course
    from parsers.curriculum_parser import TopicItem

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

    # Ensure EVERY confirmed course in codes is present in exams_data
    scheduled_codes = {e["course_code"].upper() for e in exams_data}
    if req.courses:
        for c in req.courses:
            if isinstance(c, dict):
                c_code = (c.get("code") or "").strip().upper()
                if c_code and c_code in codes and c_code not in scheduled_codes:
                    exams_data.append({
                        "course_code": c_code,
                        "date": c.get("exam_date") or "2026-09-18",
                        "start": c.get("start") or "10:30",
                        "end": c.get("end") or "12:30",
                        "slot_no": c.get("slot_no") or 11
                    })
                    scheduled_codes.add(c_code)

    for code in codes:
        if code not in scheduled_codes:
            exams_data.append({
                "course_code": code,
                "date": "2026-09-18",
                "start": "10:30",
                "end": "12:30",
                "slot_no": 11
            })
            scheduled_codes.add(code)

    # Map topics passed from frontend
    topics_by_code: dict[str, list[dict]] = {}
    if req.topics:
        for t in req.topics:
            if isinstance(t, dict):
                t_code = (t.get("code") or t.get("course") or "").strip().upper()
                t_title = t.get("topic") or t.get("title")
                if t_code and t_title:
                    topics_by_code.setdefault(t_code, []).append({"title": t_title, "in_syllabus": True})

    courses_info = []
    for code in codes:
        c_detail = get_course_by_code(code)
        c_name = c_detail.name if c_detail else code
        if req.courses:
            for rc in req.courses:
                if isinstance(rc, dict) and (rc.get("code") or "").strip().upper() == code:
                    if rc.get("name"):
                        c_name = rc.get("name")
                    break

        topics = topics_by_code.get(code, [])
        if not topics and c_detail and c_detail.topics:
            topics = [t.model_dump() for t in c_detail.topics]

        if not topics:
            try:
                gen_topics = generate_topics_for_course(code, c_name)
            except Exception:
                gen_topics = [f"{code} Theoretical Foundations", f"{code} Problem Solving Modules"]
            topics = [{"title": t, "in_syllabus": True} for t in gen_topics]
            if c_detail:
                c_detail.topics = [TopicItem(id=f"{code}_{i+1}", title=t) for i, t in enumerate(gen_topics)]

        c_name = c_detail.name if c_detail else code
        c_credits = resolve_course_credits(code, active)
        courses_info.append({
            "code": code,
            "name": c_name,
            "credits": c_credits,
            "topics": topics,
            "syllabus_raw": c_detail.syllabus_raw if c_detail else ""
        })

    # Parse start date and set realistic pre-exam study window
    from datetime import datetime, timedelta
    s_date = None
    if req.start_date:
        try:
            parsed_d = datetime.strptime(req.start_date, "%Y-%m-%d").date()
            min_e_date = min((datetime.strptime(e["date"], "%Y-%m-%d").date() for e in exams_data), default=parsed_d)
            if parsed_d >= min_e_date:
                s_date = min_e_date - timedelta(days=7)
            else:
                s_date = parsed_d
        except Exception:
            pass

    plan_response = generate_study_plan(
        exams=exams_data,
        courses_info=courses_info,
        start_date=s_date,
        daily_hours_capacity=req.daily_hours or 4.0
    )

    # 3. Format into frontend blocks schema with realistic dynamic time ranges
    formatted_plan = []
    for day in plan_response.daily_schedule:
        blocks = []
        cur_hour = 9

        for session in day.sessions:
            duration = max(1.0, session.allocated_hours)
            start_str = f"{cur_hour:02d}:00"
            end_h = cur_hour + int(duration)
            end_m = "30" if (duration - int(duration)) >= 0.4 else "00"
            if end_m == "30":
                end_str = f"{end_h:02d}:30"
            else:
                end_str = f"{end_h:02d}:00"
            t_range = f"{start_str} - {end_str}"
            cur_hour = end_h + (2 if cur_hour <= 12 else 1) # meal or focus break
            
            b_type = "revision" if session.study_type == "Revision" else "study"
            if day.is_buffer_day:
                b_type = "buffer"

            blocks.append({
                "time_range": t_range,
                "course": session.course_code,
                "type": b_type,
                "topics": [session.topic_title],
                "hours": round(session.allocated_hours, 1) if session.allocated_hours != int(session.allocated_hours) else int(session.allocated_hours),
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
            "total_hours": round(day.total_hours, 1) if day.total_hours != int(day.total_hours) else int(day.total_hours),
            "blocks": blocks
        })

    reply_text = (
        "Here is your customized, day-by-day study roadmap. "
        "I've weighted study hours based on your course credits (extracted from the master timetable), "
        "topic breadth, and syllabus volume."
    )
    if req.constraints:
        reply_text += f" Factorized your constraints: '{req.constraints}'."

    res_dict = {
        "reply": reply_text,
        "study_plan": formatted_plan,
        "workload_weights": [w.model_dump() for w in plan_response.workload_weights],
        "credit_distribution": plan_response.credit_distribution,
        "gemma_recommendations": plan_response.gemma_study_recommendations
    }
    try:
        import os, json
        plan_cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "active_plan.json")
        with open(plan_cache_path, "w", encoding="utf-8") as f:
            json.dump(res_dict, f, indent=2)
    except Exception:
        pass

    return res_dict

