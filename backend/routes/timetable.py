import json
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

try:
    from parsers.timetable_parser import (
        MasterTimetable,
        PersonalTimetableResponse,
        parse_timetable_pdf,
        parse_timetable_text,
        generate_personal_schedule,
        get_active_timetable,
        set_active_timetable,
        get_default_master_timetable,
        resolve_course_credits,
        ExamSlot,
        CourseExamEntry,
        HallAllocation,
    )
    from parsers.curriculum_parser import (
        sync_courses_from_timetable,
        reset_courses_to_default,
        get_course_by_code,
    )
    from llm import llm
except (ImportError, ValueError):
    from ..parsers.timetable_parser import (
        MasterTimetable,
        PersonalTimetableResponse,
        parse_timetable_pdf,
        parse_timetable_text,
        generate_personal_schedule,
        get_active_timetable,
        set_active_timetable,
        get_default_master_timetable,
        resolve_course_credits,
        ExamSlot,
        CourseExamEntry,
        HallAllocation,
    )
    from ..parsers.curriculum_parser import (
        sync_courses_from_timetable,
        reset_courses_to_default,
        get_course_by_code,
    )
    from ..llm import llm


router = APIRouter(prefix="/api/timetable", tags=["Timetable"])

class EnrolledCoursesRequest(BaseModel):
    enrolled_courses: List[str]

@router.post("/upload", summary="Upload and parse a new master timetable PDF or JSON")
async def upload_timetable(
    file: UploadFile = File(...)
):
    """
    User/Admin uploads the latest master exam timetable PDF or JSON.
    - The timetable is dynamically parsed.
    - Set as the active timetable.
    - Overwrites course offerings and instructors based on this live timetable.
    - Returns exact JSON format expected by the frontend.
    """
    content = await file.read()
    filename = file.filename.lower() if file.filename else ""

    try:
        content_type = file.content_type or ""
        is_image = any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]) or "image" in content_type

        if filename.endswith(".json"):
            data = json.loads(content.decode("utf-8"))
            parsed_timetable = MasterTimetable.model_validate(data)
        elif filename.endswith(".pdf"):
            parsed_timetable = parse_timetable_pdf(content)
        elif is_image:
            mime = content_type if "image" in content_type else "image/png"
            items = llm.extract_timetable_from_image(content, mime)
            parsed_timetable = MasterTimetable(session="2026-27")
            if items:
                for idx, it in enumerate(items, 1):
                    c_name = it.get("name") or it.get("code") or f"Course-{idx}"
                    e_date = it.get("exam_date") or "2026-11-20"
                    slot = ExamSlot(
                        slot_no=idx,
                        date=e_date,
                        start="10:00",
                        end="13:00",
                        courses=[CourseExamEntry(
                            codes=[c_name],
                            instructors=["Faculty"],
                            students=60,
                            halls=[HallAllocation(hall="L-209", assigned=60)]
                        )]
                    )
                    parsed_timetable.slots.append(slot)
            else:
                text_str = content.decode("utf-8", errors="ignore")
                parsed_timetable = parse_timetable_text(text_str)
        else:
            text_str = content.decode("utf-8", errors="ignore")
            parsed_timetable = parse_timetable_text(text_str)

        fallback_used = False
        if not parsed_timetable.slots:
            parsed_timetable = get_default_master_timetable()
            fallback_used = True

        # 1. Update active timetable in memory and persist
        set_active_timetable(parsed_timetable)
        try:
            import os
            tt_disk_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
            with open(tt_disk_path, "w", encoding="utf-8") as f:
                json.dump(parsed_timetable.model_dump(), f, indent=2)
        except Exception:
            pass

        # 2. Overwrite & synchronize course instructors and active offerings from this timetable
        sync_stats = sync_courses_from_timetable(parsed_timetable.slots)

        # 3. Format extracted courses for frontend consumption
        extracted_courses = []
        seen_codes = set()
        min_date = None

        for slot in parsed_timetable.slots:
            if not min_date or slot.date < min_date:
                min_date = slot.date
            for c_entry in slot.courses:
                for code in c_entry.codes:
                    clean_code = code.strip().upper()
                    if clean_code not in seen_codes:
                        seen_codes.add(clean_code)
                        c_info = get_course_by_code(clean_code)
                        c_name = c_info.name if c_info else clean_code
                        instructor = ", ".join(c_entry.instructors) if c_entry.instructors else "Institute Faculty"
                        hall = c_entry.halls[0].hall if c_entry.halls else "Exam Hall"
                        c_credits = c_entry.credits or resolve_course_credits(clean_code, parsed_timetable)
                        extracted_courses.append({
                            "code": clean_code,
                            "name": c_name,
                            "credits": float(c_credits),
                            "instructor": instructor,
                            "exam_date": slot.date,
                            "slot_no": slot.slot_no,
                            "hall": hall,
                            "start": slot.start,
                            "end": slot.end
                        })

        if fallback_used:
            reply_msg = (
                f"I've analyzed your uploaded document! Because custom exam dates couldn't be unambiguously extracted, "
                f"I've loaded the institute's default examination timetable for session {parsed_timetable.session}. "
                "Please confirm your enrolled courses below."
            )
        else:
            reply_msg = (
                f"I've successfully parsed your examination timetable for session {parsed_timetable.session}! "
                f"Identified {len(extracted_courses)} courses across {len(parsed_timetable.slots)} slots. "
                "Please confirm the ones you are enrolled in below."
            )

        return {
            "status": "success",
            "reply": reply_msg,
            "extracted_data": {
                "courses": extracted_courses,
                "study_hours": 4,
                "start_date": min_date or "2026-09-18"
            },
            "total_slots": len(parsed_timetable.slots),
            "session": parsed_timetable.session,
            "exam_type": parsed_timetable.exam_type,
            "course_sync_summary": sync_stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse uploaded timetable: {str(e)}")


@router.get("", summary="Get current active master timetable")
def get_current_timetable(use_default_if_empty: bool = False):
    """
    Returns the currently active uploaded timetable.
    If no timetable was uploaded, returns 404 (or default fallback only if explicitly requested).
    """
    active = get_active_timetable()
    if active:
        return active
    
    if use_default_if_empty:
        import os
        sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return MasterTimetable.model_validate(data)
                
    raise HTTPException(
        status_code=404,
        detail="No active timetable has been uploaded yet. Please upload the latest master timetable via POST /api/timetable/upload."
    )

@router.post("/personal", response_model=PersonalTimetableResponse, summary="Generate personalized exam schedule")
def get_personal_schedule(request: EnrolledCoursesRequest):
    """
    Reconciles student's enrolled courses with the active uploaded timetable:
    - Matches cross-listed aliases ('/')
    - Alerts on slot clashes (same slot/time)
    - Alerts on tight gaps (< 24 hrs between consecutive exams)
    """
    active = get_active_timetable()
    if not active:
        raise HTTPException(
            status_code=400,
            detail="No timetable uploaded yet. Please upload the master timetable first via POST /api/timetable/upload."
        )

    return generate_personal_schedule(request.enrolled_courses, active)

@router.delete("", summary="Clear the active timetable and restore default courses")
def clear_timetable():
    set_active_timetable(None)
    reset_courses_to_default()
    return {
        "status": "cleared",
        "message": "Active timetable removed and courses restored to baseline defaults."
    }
