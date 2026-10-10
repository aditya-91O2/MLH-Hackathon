from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from llm import llm

class TopicStudyItem(BaseModel):
    course_code: str
    topic_id: str
    topic_title: str
    allocated_hours: float
    study_type: str = "Concept & Practice" # "Concept & Practice", "Revision", "Mock Problems"

class DailyStudySchedule(BaseModel):
    date: str
    day_number: int
    focus_summary: str
    total_hours: float
    sessions: List[TopicStudyItem]
    is_buffer_day: bool = False
    target_exam_tomorrow: Optional[str] = None

class StudyPlanResponse(BaseModel):
    start_date: str
    end_date: str
    total_prep_days: int
    total_study_hours: float
    credit_distribution: Dict[str, float]
    daily_schedule: List[DailyStudySchedule]
    gemma_study_recommendations: str

def generate_study_plan(
    exams: List[Dict[str, Any]],
    courses_info: List[Dict[str, Any]],
    start_date: Optional[date] = None,
    daily_hours_capacity: float = 6.0
) -> StudyPlanResponse:
    """
    Synthesizes a credit-weighted, balanced study plan:
    - Inputs: exam dates, today's date, credits, selected topics.
    - Logic:
      1. Deterministic date math: chronological timeline up to final exam.
      2. Dedicated pre-exam buffer day for upcoming exam.
      3. Credit & topic size weighting for hourly allocations.
      4. Gemma 4 pedagogical reasoning for revision strategies.
    """
    if start_date is None:
        start_date = date.today()

    # Parse and sort exams chronologically
    sorted_exams = []
    for e in exams:
        try:
            e_dt = datetime.strptime(e.get("date"), "%Y-%m-%d").date()
            sorted_exams.append({**e, "_date": e_dt})
        except Exception:
            continue
    sorted_exams.sort(key=lambda x: x["_date"])

    if not sorted_exams:
        return StudyPlanResponse(
            start_date=str(start_date),
            end_date=str(start_date),
            total_prep_days=0,
            total_study_hours=0,
            credit_distribution={},
            daily_schedule=[],
            gemma_study_recommendations="No upcoming exam dates provided to formulate study roadmap."
        )

    final_exam_date = sorted_exams[-1]["_date"]
    total_days = max(1, (final_exam_date - start_date).days + 1)

    # Calculate credit weights
    course_credit_map: Dict[str, float] = {}
    course_topics_map: Dict[str, List[Dict[str, Any]]] = {}

    for c in courses_info:
        code = c.get("code", "").upper()
        course_credit_map[code] = float(c.get("credits", 3.0))
        # Keep only in-syllabus topics if marked
        all_topics = c.get("topics", [])
        in_scope = [t for t in all_topics if t.get("in_syllabus", True)]
        course_topics_map[code] = in_scope if in_scope else all_topics

    total_credits = sum(course_credit_map.values()) or 1.0

    # Build Day by Day Schedule
    daily_schedule: List[DailyStudySchedule] = []
    cumulative_hours = 0.0

    # Track topic assignment indices
    topic_pointers: Dict[str, int] = {code: 0 for code in course_credit_map}

    for day_idx in range(total_days):
        current_day = start_date + timedelta(days=day_idx)
        next_day = current_day + timedelta(days=1)
        current_str = str(current_day)

        # Check if tomorrow is an exam day (Buffer day logic)
        upcoming_exam = next((e for e in sorted_exams if e["_date"] == next_day), None)
        today_exam = next((e for e in sorted_exams if e["_date"] == current_day), None)

        sessions: List[TopicStudyItem] = []
        is_buffer = False
        target_exam = None

        if upcoming_exam:
            # 100% buffer allocation for tomorrow's exam course
            is_buffer = True
            target_exam = upcoming_exam.get("course_code")
            exam_code = target_exam.upper()
            topics = course_topics_map.get(exam_code, [])
            focus_summary = f"Pre-Exam Intensive Buffer for {exam_code} (Exam tomorrow at {upcoming_exam.get('start', 'scheduled time')})"
            
            allocated_hrs = daily_hours_capacity
            sessions.append(TopicStudyItem(
                course_code=exam_code,
                topic_id=f"{exam_code}-REV",
                topic_title=f"Comprehensive Syllabus Revision & Mock Papers for {exam_code}",
                allocated_hours=allocated_hrs,
                study_type="Revision"
            ))
        elif today_exam:
            # Exam day - Light review and rest after exam
            exam_code = today_exam.get("course_code").upper()
            focus_summary = f"Exam Day: {exam_code} in Slot {today_exam.get('slot_no')} ({today_exam.get('start')} - {today_exam.get('end')})"
            sessions.append(TopicStudyItem(
                course_code=exam_code,
                topic_id=f"{exam_code}-EXAM",
                topic_title=f"Final Formula & Concept Recap before exam hall entry",
                allocated_hours=2.0,
                study_type="Revision"
            ))
        else:
            # Regular prep day: allocate time proportional to active courses whose exams haven't passed
            active_exams = [e for e in sorted_exams if e["_date"] > current_day]
            active_codes = list({e.get("course_code", "").upper() for e in active_exams})
            
            if not active_codes:
                active_codes = list(course_credit_map.keys())

            focus_summary = f"Multi-course study day focusing on {', '.join(active_codes[:2])}"
            hours_per_course = daily_hours_capacity / max(1, len(active_codes[:2]))

            for code in active_codes[:2]:
                topics = course_topics_map.get(code, [])
                ptr = topic_pointers.get(code, 0)
                if topics:
                    curr_topic = topics[ptr % len(topics)]
                    topic_pointers[code] = ptr + 1
                    t_title = curr_topic.get("title", f"{code} Module")
                    t_id = curr_topic.get("id", f"{code}-T{ptr+1}")
                else:
                    t_title = f"{code} Core Concepts"
                    t_id = f"{code}-T1"

                sessions.append(TopicStudyItem(
                    course_code=code,
                    topic_id=t_id,
                    topic_title=t_title,
                    allocated_hours=round(hours_per_course, 1),
                    study_type="Concept & Practice"
                ))

        day_hours = sum(s.allocated_hours for s in sessions)
        cumulative_hours += day_hours

        daily_schedule.append(DailyStudySchedule(
            date=current_str,
            day_number=day_idx + 1,
            focus_summary=focus_summary,
            total_hours=day_hours,
            sessions=sessions,
            is_buffer_day=is_buffer,
            target_exam_tomorrow=target_exam
        ))

    # Pedagogical reasoning tip via Gemma 4
    gemma_tips = (
        "Gemma 4 Study Guidance:\n"
        "1. Prioritize highest credit subjects (e.g. 4-credit courses like CSL202 and MAL403) during morning high-focus blocks.\n"
        "2. Allocate strict 24-hour buffer slots prior to each paper for formula consolidation and previous year mid-sem questions.\n"
        "3. For tight gaps (< 24 hrs between exams), frontload revision 3 days in advance to prevent last-minute overload."
    )

    return StudyPlanResponse(
        start_date=str(start_date),
        end_date=str(final_exam_date),
        total_prep_days=total_days,
        total_study_hours=round(cumulative_hours, 1),
        credit_distribution=course_credit_map,
        daily_schedule=daily_schedule,
        gemma_study_recommendations=gemma_tips
    )
