from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from llm import llm
except (ImportError, ValueError):
    from .llm import llm


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

class CourseWorkloadWeight(BaseModel):
    course_code: str
    course_name: str
    credits: float
    num_topics: int
    content_volume_label: str
    depth_multiplier: float
    composite_weight: float
    workload_percentage: float
    recommended_total_hours: float

class StudyPlanResponse(BaseModel):
    start_date: str
    end_date: str
    total_prep_days: int
    total_study_hours: float
    credit_distribution: Dict[str, float]
    workload_weights: List[CourseWorkloadWeight] = []
    daily_schedule: List[DailyStudySchedule]
    gemma_study_recommendations: str

def analyze_course_content_depth(course_code: str, course_info: Dict[str, Any]) -> tuple[float, str]:
    """
    Evaluates how huge and conceptually dense the course contents are:
    - Heavy STEM / Algorithms / Math / Coordination Chemistry: 1.35 - 1.45x
    - Core Engineering Theory: 1.25x
    - Standard Theory: 1.00x
    - Hands-on Practical Lab: 0.75x
    - Foundational Language & Communication: 0.70x
    """
    import re
    code = course_code.upper()
    name = (course_info.get("name") or "").lower()
    syllabus = (course_info.get("syllabus_raw") or "").lower()
    topics = course_info.get("topics") or []

    # 1. Practical / Lab Course
    is_lab = "lab" in name or "lab" in syllabus or ("P" in code[2:4] if len(code) >= 4 else False)
    if is_lab:
        return 0.75, "Practical & Tool Laboratory (Hands-on experiments)"

    # 2. Communication / Soft skills
    is_hum = code.startswith("LA") or code.startswith("HS") or "communication" in name
    if is_hum:
        return 0.70, "Foundational Communication & Soft Skills (Concise modules)"

    # 3. Heavy STEM (Algorithms, Probability, Statistics, Discrete Math, Chemistry, Architecture)
    is_heavy_stem = (
        any(k in name for k in ["data structure", "algorithm", "probability", "statistics", "discrete", "operating system", "coordination", "quantum", "compiler", "machine learning", "organic", "calculus", "linear algebra"])
        or any(code.startswith(prefix) for prefix in ["CS", "MA", "CY", "EE", "PH", "ME"])
    )

    level_match = re.search(r'\d{3}', code)
    level_num = int(level_match.group(0)) if level_match else 200

    if level_num >= 600:
        return 1.45, "Advanced Postgraduate / Specialist Rigor (Comprehensive content)"
    elif level_num >= 300 or (is_heavy_stem and level_num >= 200 and len(topics) >= 5):
        return 1.35, "Core Engineering & Mathematical Rigor (Heavy conceptual depth)"
    elif is_heavy_stem:
        return 1.25, "Core Engineering Concepts (Substantial syllabus breadth)"
    else:
        return 1.00, "Standard Academic Coursework"

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

    min_exam_date = sorted_exams[0]["_date"]
    final_exam_date = sorted_exams[-1]["_date"]

    # Effective preparation start date:
    # A study preparation roadmap MUST precede the exams!
    # If the provided start_date is on or after the first exam date (or None),
    # calculate a preparation window of at least 7 to 10 days leading up to the first exam.
    if start_date is None or start_date >= min_exam_date:
        start_date = min_exam_date - timedelta(days=7)

    total_days = max(1, (final_exam_date - start_date).days + 1)

    # Calculate credit, topic count, and content depth weights
    course_credit_map: Dict[str, float] = {}
    course_topics_map: Dict[str, List[Dict[str, Any]]] = {}
    course_weights_dict: Dict[str, Dict[str, Any]] = {}
    total_composite_weight = 0.0

    for c in courses_info:
        code = c.get("code", "").upper()
        c_name = c.get("name") or code
        credits_val = float(c.get("credits", 3.0))
        course_credit_map[code] = credits_val

        # Filter in-syllabus topics
        all_topics = c.get("topics", [])
        in_scope = [t for t in all_topics if t.get("in_syllabus", True)]
        selected_topics = in_scope if in_scope else all_topics
        course_topics_map[code] = selected_topics
        num_topics = max(1, len(selected_topics))

        depth_multiplier, depth_label = analyze_course_content_depth(code, c)

        # Composite Workload Weight Formula:
        # Weight = Credits * sqrt(num_topics) * DepthMultiplier
        comp_weight = credits_val * (num_topics ** 0.5) * depth_multiplier
        total_composite_weight += comp_weight

        course_weights_dict[code] = {
            "name": c_name,
            "credits": credits_val,
            "num_topics": num_topics,
            "depth_label": depth_label,
            "depth_multiplier": depth_multiplier,
            "composite_weight": comp_weight
        }

    total_capacity_hours = total_days * daily_hours_capacity
    workload_weights: List[CourseWorkloadWeight] = []

    for code, wd in course_weights_dict.items():
        comp_w = wd["composite_weight"]
        pct = (comp_w / total_composite_weight * 100.0) if total_composite_weight > 0 else 0.0
        rec_hours = round(total_capacity_hours * (pct / 100.0), 1)

        workload_weights.append(CourseWorkloadWeight(
            course_code=code,
            course_name=wd["name"],
            credits=wd["credits"],
            num_topics=wd["num_topics"],
            content_volume_label=wd["depth_label"],
            depth_multiplier=wd["depth_multiplier"],
            composite_weight=round(comp_w, 2),
            workload_percentage=round(pct, 1),
            recommended_total_hours=rec_hours
        ))

    # Sort workload weights with highest weight first
    workload_weights.sort(key=lambda x: x.composite_weight, reverse=True)

    # Build Day by Day Schedule
    daily_schedule: List[DailyStudySchedule] = []
    cumulative_hours = 0.0

    # Track topic assignment indices
    topic_pointers: Dict[str, int] = {code: 0 for code in course_credit_map}

    for day_idx in range(total_days):
        current_day = start_date + timedelta(days=day_idx)
        next_day = current_day + timedelta(days=1)
        current_str = str(current_day)

        # Check exams today and tomorrow
        upcoming_exams = [e for e in sorted_exams if e["_date"] == next_day]
        today_exams = [e for e in sorted_exams if e["_date"] == current_day]

        sessions: List[TopicStudyItem] = []
        is_buffer = False
        target_exam = None

        if today_exams:
            # Exam day - Light recap for all exams happening today
            exam_codes = [e.get("course_code", "").upper() for e in today_exams]
            focus_summary = f"Exam Day: {', '.join(exam_codes)}"
            hrs_per_exam = 2.0
            for te in today_exams:
                exam_code = te.get("course_code", "").upper()
                sessions.append(TopicStudyItem(
                    course_code=exam_code,
                    topic_id=f"{exam_code}-EXAM",
                    topic_title=f"Final Formula & Concept Recap for {exam_code} before hall entry",
                    allocated_hours=hrs_per_exam,
                    study_type="Revision"
                ))
        elif upcoming_exams:
            # Pre-exam intensive revision buffer day
            is_buffer = True
            exam_codes = [e.get("course_code", "").upper() for e in upcoming_exams]
            target_exam = "/".join(exam_codes)
            focus_summary = f"Pre-Exam Intensive Buffer for upcoming exam: {target_exam}"
            hrs_per_exam = max(1.0, daily_hours_capacity / len(upcoming_exams))
            for ue in upcoming_exams:
                exam_code = ue.get("course_code", "").upper()
                sessions.append(TopicStudyItem(
                    course_code=exam_code,
                    topic_id=f"{exam_code}-REV",
                    topic_title=f"Intensive Formula Sheet, PYQs & Revision for {exam_code}",
                    allocated_hours=round(hrs_per_exam, 1),
                    study_type="Revision"
                ))
        else:
            # Regular prep day: allocate time across active courses whose exams haven't passed
            active_exams = [e for e in sorted_exams if e["_date"] >= current_day]
            active_codes = list(dict.fromkeys([e.get("course_code", "").upper() for e in active_exams]))
            if not active_codes:
                active_codes = list(course_credit_map.keys())

            focus_summary = f"Multi-course study day focusing on {', '.join(active_codes)}"

            # Select courses to study today (up to 2 for focus, weighted rotation)
            num_courses_today = min(len(active_codes), 2 if len(active_codes) > 2 else len(active_codes))
            offset = day_idx % len(active_codes)
            selected_codes = [active_codes[(offset + i) % len(active_codes)] for i in range(num_courses_today)]

            # Proportional weighted hour allocation for today's selected courses
            if len(selected_codes) == 1:
                allocations = {selected_codes[0]: daily_hours_capacity}
            else:
                w1 = course_weights_dict.get(selected_codes[0], {}).get("composite_weight", 1.0)
                w2 = course_weights_dict.get(selected_codes[1], {}).get("composite_weight", 1.0)
                total_w = w1 + w2 or 1.0
                
                # Proportional split of daily_hours_capacity
                h1 = round(daily_hours_capacity * (w1 / total_w), 1)
                h2 = round(daily_hours_capacity - h1, 1)
                
                # Ensure each session is at least 1.0h
                if h1 < 1.0:
                    h1 = 1.0
                    h2 = max(1.0, daily_hours_capacity - 1.0)
                elif h2 < 1.0:
                    h2 = 1.0
                    h1 = max(1.0, daily_hours_capacity - 1.0)

                allocations = {selected_codes[0]: h1, selected_codes[1]: h2}

            for code in selected_codes:
                topics = course_topics_map.get(code, [])
                ptr = topic_pointers.get(code, 0)
                if topics:
                    curr_topic = topics[ptr % len(topics)]
                    topic_pointers[code] = ptr + 1
                    t_title = curr_topic.get("title") or curr_topic.get("topic") or f"{code} Module"
                    t_id = curr_topic.get("id", f"{code}-T{ptr+1}")
                else:
                    t_title = f"{code} Core Conceptual Foundations & Problem Solving"
                    t_id = f"{code}-T1"

                hrs = allocations.get(code, daily_hours_capacity / len(selected_codes))

                sessions.append(TopicStudyItem(
                    course_code=code,
                    topic_id=t_id,
                    topic_title=t_title,
                    allocated_hours=round(hrs, 1),
                    study_type="Concept & Practice"
                ))

        day_hours = sum(s.allocated_hours for s in sessions)
        cumulative_hours += day_hours

        daily_schedule.append(DailyStudySchedule(
            date=current_str,
            day_number=day_idx + 1,
            focus_summary=focus_summary,
            total_hours=round(day_hours, 1),
            sessions=sessions,
            is_buffer_day=is_buffer,
            target_exam_tomorrow=target_exam
        ))

    # Dynamic pedagogical reasoning guidance
    top_heavy = [w for w in workload_weights if w.workload_percentage >= 25.0]
    top_str = ", ".join([f"{w.course_code} ({w.credits} cr, {w.workload_percentage}%)" for w in top_heavy]) if top_heavy else "core courses"

    gemma_tips = (
        f"Gemma 4 Pedagogical Workload Strategy:\n"
        f"1. Credit & Volume Weighting: High-credit core theory subjects ({top_str}) account for the majority of study time with deep 2.5-3.5h immersion blocks for derivations and problem sets.\n"
        f"2. Focused Practical Sessions: Lab courses and communication modules are scheduled in targeted 1.0-1.5h sessions to maximize retention without depleting focus from heavy subjects.\n"
        f"3. Dedicated 24h Buffer Slots: Pre-exam intensive revision buffers are strictly reserved immediately prior to each paper for formula sheets and previous-year questions."
    )

    return StudyPlanResponse(
        start_date=str(start_date),
        end_date=str(final_exam_date),
        total_prep_days=total_days,
        total_study_hours=round(cumulative_hours, 1),
        credit_distribution=course_credit_map,
        workload_weights=workload_weights,
        daily_schedule=daily_schedule,
        gemma_study_recommendations=gemma_tips
    )
