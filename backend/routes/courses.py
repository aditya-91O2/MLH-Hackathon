import re
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

try:
    from parsers.curriculum_parser import (
        get_semester_courses,
        get_course_by_code,
        get_active_courses,
        load_default_courses,
        CourseDetail,
        TopicItem
    )
    from llm import llm
except (ImportError, ValueError):
    from ..parsers.curriculum_parser import (
        get_semester_courses,
        get_course_by_code,
        get_active_courses,
        load_default_courses,
        CourseDetail,
        TopicItem
    )
    from ..llm import llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/courses", tags=["Courses & Curriculum"])

class TopicScopeRequest(BaseModel):
    course_code: str
    included_topic_ids: List[str]
    excluded_topic_ids: List[str] = []

@router.get("", summary="Get courses for branch and semester")
def get_courses(
    branch: str = Query("CSE", description="Academic branch code, e.g. CSE, DSAI, EE"),
    semester: str = Query("3", description="Semester number (1-8)"),
    only_offered: bool = Query(False, description="Filter only courses currently offered this semester based on master timetable")
):
    """
    Returns default semester curriculum courses.
    If a master timetable was uploaded, course instructor information and offering status
    are automatically enriched/overwritten.
    """
    return get_semester_courses(branch, semester, only_offered=only_offered)

@router.get("/all", summary="List all courses in active catalog")
def get_all_courses(only_offered: bool = Query(False, description="Filter only courses offered this semester")):
    courses = get_active_courses()
    if only_offered:
        return [c for c in courses if c.is_offered_this_sem]
    return courses

@router.get("/defaults", summary="Get pristine baseline courses from Course of Study")
def get_default_catalog():
    return load_default_courses()

@router.get("/{code}", response_model=CourseDetail, summary="Get course details and syllabus topics")
def get_course(code: str):
    course = get_course_by_code(code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{code}' not found.")
    return course

@router.post("/scope", summary="Set in-syllabus vs excluded topics for an exam")
def set_course_topic_scope(scope: TopicScopeRequest):
    course = get_course_by_code(scope.course_code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{scope.course_code}' not found.")
    
    scoped_topics = []
    for topic in course.topics:
        is_in = topic.id in scope.included_topic_ids and topic.id not in scope.excluded_topic_ids
        scoped_topics.append({
            "id": topic.id,
            "title": topic.title,
            "subtopics": topic.subtopics,
            "in_syllabus": is_in
        })

    return {
        "course_code": course.code,
        "total_topics": len(course.topics),
        "in_syllabus_count": sum(1 for t in scoped_topics if t["in_syllabus"]),
        "topics": scoped_topics
    }

DEPT_NAMES = {
    "CY": "Chemistry",
    "CS": "Computer Science and Engineering",
    "ME": "Mechanical Engineering",
    "EE": "Electrical Engineering",
    "EC": "Electronics and Communication Engineering",
    "PH": "Physics",
    "MA": "Mathematics",
    "CE": "Civil Engineering",
    "CH": "Chemical Engineering",
    "BT": "Biotechnology",
    "BM": "Biomedical Engineering",
    "MT": "Materials and Metallurgical Engineering",
    "HU": "Humanities and Social Sciences",
    "HS": "Humanities and Social Sciences",
    "LA": "Language and Communication Skills",
}

def generate_topics_for_course(code: str, course_name: str, instructor: str = "") -> List[str]:
    """
    Decomposes a course code/name into authentic university syllabus modules using Gemma 4,
    with an authoritative IIT domain fallback for physics, chemistry, engineering, etc.
    """
    # 1. Ask Gemma 4 / Gemini
    try:
        dept = DEPT_NAMES.get(code[:2].upper(), "Engineering and Sciences")
        inst_clause = f"\nInstructor / Faculty: {instructor}" if instructor else ""
        prompt = (
            f"You are an expert academic curriculum professor at an Indian Institute of Technology (IIT).\n"
            f"Deconstruct the university course with course code '{code}', course title '{course_name}', department '{dept}'{inst_clause} into exactly 4 to 6 specific, authentic exam syllabus module topics.\n"
            f"Rules:\n"
            f"- Return ONLY specific academic/scientific/engineering topic names for this course.\n"
            f"- Do NOT use generic placeholder words like 'Core Foundations of {code}' or 'Theory & Foundations'.\n"
            f"- Format as a strict JSON array of strings: [\"Topic 1\", \"Topic 2\", ...]\n"
            f"Respond with JSON only."
        )
        resp = llm.generate_text(prompt)
        if resp:
            cleaned = resp.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            s_idx = cleaned.find("[")
            e_idx = cleaned.rfind("]")
            if s_idx != -1 and e_idx != -1:
                parsed = json.loads(cleaned[s_idx:e_idx+1])
                if isinstance(parsed, list):
                    res = []
                    for item in parsed:
                        if isinstance(item, dict):
                            val = item.get("title") or item.get("topic") or str(item)
                            if val: res.append(val.strip())
                        elif isinstance(item, str) and item.strip():
                            res.append(item.strip())
                    if len(res) >= 3:
                        return res[:6]
    except Exception as e:
        logger.warning(f"Gemma 4 topic generation failed for {code}: {e}")

    # 2. Rich Academic IIT Knowledge Bank Fallback
    prefix = re.sub(r"[^A-Z]", "", code[:3].upper())
    num_part = re.sub(r"\D", "", code)
    is_advanced = int(num_part) >= 400 if num_part else False

    if code.upper() == "CYL609":
        return [
            "Crystal Engineering & Non-Covalent Interactions",
            "Metal-Organic Frameworks (MOFs) & Coordination Polymers",
            "Supramolecular Chemistry & Molecular Recognition",
            "Design & Synthesis of Porous Crystalline Materials",
            "Stimuli-Responsive Functional Materials & Solid-State Transformations"
        ]
    elif prefix in ("PHL", "PHP", "PH"):
        if is_advanced:
            return [
                "Advanced Quantum Mechanics & Perturbation Theory",
                "Electromagnetic Radiation & Waveguides",
                "Statistical Mechanics & Quantum Ensembles",
                "Solid State Physics, Phonons & Band Structure",
                "Lasers, Non-Linear Optics & Photonics"
            ]
        return [
            "Classical Mechanics & Harmonic Oscillators",
            "Maxwell's Equations & Electromagnetic Waves",
            "Wave Optics, Interference & Diffraction",
            "Special Relativity & Four-Vectors",
            "Introduction to Quantum States & Wave Functions"
        ]
    elif prefix in ("CYL", "CYP", "CY"):
        if is_advanced:
            return [
                "Coordination Chemistry & Transition Metal Complexes",
                "Advanced Organic Synthesis & Reaction Mechanisms",
                "Quantum Chemistry & Molecular Spectroscopy",
                "Supramolecular Chemistry & Nanomaterials",
                "Chemical Kinetics, Catalysis & Organometallics"
            ]
        return [
            "Chemical Thermodynamics, Phase Rule & Equilibria",
            "Quantum Chemistry & Molecular Orbital Theory",
            "Chemical Kinetics, Catalysis & Reaction Mechanisms",
            "Coordination Chemistry & Transition Metal Complexes",
            "Spectroscopic Identification: UV-Vis, IR & NMR"
        ]
    elif prefix in ("MEL", "MEP", "ME"):
        return [
            "Applied Thermodynamics & Gas Power Cycles",
            "Fluid Mechanics: Boundary Layer & Navier-Stokes",
            "Mechanics of Solids: 3D Stress & Strain Tensors",
            "Heat Transfer: Conduction, Convection & Radiation",
            "Kinematics & Dynamic Balancing of Machinery"
        ]
    elif prefix in ("EEL", "EEP", "ECL", "EE", "EC"):
        return [
            "Continuous & Discrete-Time Signals and Systems",
            "Analog Circuit Design & Operational Amplifiers",
            "Digital Logic Design, Verilog & Microprocessors",
            "Linear Feedback Control Systems & Stability",
            "Electromagnetic Fields & Wave Propagation"
        ]
    elif prefix in ("MAL", "MA"):
        return [
            "Linear Algebra, Eigenvalues & Matrix Factorizations",
            "Multivariable Calculus & Vector Integration",
            "Ordinary & Partial Differential Equations",
            "Probability Theory, Random Variables & Distributions",
            "Numerical Analysis & Iterative Optimization"
        ]
    elif prefix in ("CSL", "CSP", "CS"):
        return [
            "Advanced Data Structures & Graph Algorithms",
            "Algorithm Design Paradigms & Asymptotic Complexity",
            "Operating Systems: Concurrency, Synchronization & Memory",
            "Database Systems, Indexing & Transaction Management",
            "Computer Networks: Architecture & Transport Layer Protocols"
        ]
    elif prefix in ("HUL", "HU"):
        return [
            "Technical Writing, Proposal & Report Formatting",
            "Professional Ethics & Corporate Governance",
            "Principles of Microeconomics & Market Dynamics",
            "Sociology of Technology & Sustainable Development"
        ]
    else:
        dept_fallback = DEPT_NAMES.get(code[:2].upper(), code)
        return [
            f"Core Theoretical Principles of {dept_fallback}",
            f"Mathematical Modelling & Analytical Methods in {code}",
            f"Advanced Problem Solving & Methodologies in {code}",
            f"Applied Systems, Experimental Design & Instrumentation",
            f"Key Case Studies, Problem Sets & Comprehensive Review"
        ]

class CourseTopicsBatchRequest(BaseModel):
    courses: Optional[List[dict]] = None
    course_codes: Optional[List[str]] = None

@router.post("/topics", summary="Get decomposed topics for selected courses")
def get_topics_for_selected_courses(req: CourseTopicsBatchRequest):
    """
    Returns mapped topics for confirmed courses matching frontend demo format.
    Dynamically decomposes topics using Gemma 4 with rich IIT academic knowledge fallback.
    """
    codes = set()
    instructor_map = {}
    if req.course_codes:
        codes.update([c.upper().strip() for c in req.course_codes])
    if req.courses:
        for c in req.courses:
            if isinstance(c, dict) and "code" in c:
                c_code = c["code"].upper().strip()
                codes.add(c_code)
                if "instructor" in c and c["instructor"]:
                    instructor_map[c_code] = c["instructor"]
            elif isinstance(c, str):
                codes.add(c.upper().strip())

    topics_result = []
    for code in sorted(codes):
        course = get_course_by_code(code)
        course_name = course.name if course else code
        instructor = instructor_map.get(code) or (", ".join(course.instructors) if (course and course.instructors) else "")

        # Check if existing topics are authentic, specific topics (not old dummy placeholders)
        has_real_topics = False
        if course and course.topics and len(course.topics) >= 2:
            first_title = course.topics[0].title.lower()
            if not ("core foundations" in first_title or "practical applications of" in first_title):
                has_real_topics = True

        if has_real_topics and course:
            for t in course.topics:
                topics_result.append({
                    "course": course_name,
                    "code": course.code,
                    "topic": t.title,
                    "included": False
                })
        else:
            gen_topics = generate_topics_for_course(code, course_name, instructor)
            if course:
                course.topics = [TopicItem(id=f"{code}_{i+1}", title=t) for i, t in enumerate(gen_topics)]
            for t_title in gen_topics:
                topics_result.append({
                    "course": course_name,
                    "code": code,
                    "topic": t_title,
                    "included": False
                })

    return {
        "reply": f"Gemma 4 has decomposed {len(codes)} course(s) into authentic syllabus modules. Select the topics you need to focus on below:",
        "topics": topics_result
    }

