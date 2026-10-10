import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")

class TopicItem(BaseModel):
    id: str
    title: str
    subtopics: List[str] = []
    in_syllabus: bool = True

class CourseDetail(BaseModel):
    code: str
    name: str
    credits: float = 3.0
    ltp: str = "3-0-0"
    prerequisites: List[str] = []
    aliases: List[str] = []
    instructors: List[str] = []
    is_offered_this_sem: bool = True
    source: str = "CourseOfStudy" # "CourseOfStudy", "MasterTimetable", or "Enriched"
    syllabus_raw: str = ""
    topics: List[TopicItem] = []

# In-memory dynamic active course registry (populated on timetable upload, defaults to None)
_ACTIVE_COURSES_MAP: Optional[Dict[str, CourseDetail]] = None

def load_default_courses() -> List[CourseDetail]:
    """Loads pristine baseline courses from data/courses.json with safety fallbacks."""
    path = os.path.join(DATA_DIR, "courses.json")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return _get_builtin_default_courses()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return _get_builtin_default_courses()
        return [CourseDetail.model_validate(c) for c in data]
    except Exception:
        return _get_builtin_default_courses()

def _get_builtin_default_courses() -> List[CourseDetail]:
    """Builtin fallback courses if courses.json is empty or missing."""
    return [
        CourseDetail(
            code="MAL403",
            name="Probability and Statistics",
            credits=4.0,
            ltp="3-1-0",
            aliases=["IC105"],
            instructors=["Dr. Lakshmi Kanta Patra"],
            topics=[
                TopicItem(id="mal403_1", title="Axioms of Probability and Conditional Probability"),
                TopicItem(id="mal403_2", title="Random Variables and Distribution Functions"),
                TopicItem(id="mal403_3", title="Expectation, Variance, and Moments"),
                TopicItem(id="mal403_4", title="Limit Theorems: Law of Large Numbers & CLT"),
                TopicItem(id="mal403_5", title="Confidence Intervals & Hypothesis Testing")
            ]
        ),
        CourseDetail(
            code="CSL201",
            name="Discrete Mathematics",
            credits=4.0,
            ltp="3-1-0",
            aliases=["MAL503"],
            instructors=["Dr. Rishi Ranjan Singh"],
            topics=[
                TopicItem(id="csl201_1", title="Propositional and First-Order Predicate Logic"),
                TopicItem(id="csl201_2", title="Set Theory, Relations, and Equivalence"),
                TopicItem(id="csl201_3", title="Combinatorics and Pigeonhole Principle"),
                TopicItem(id="csl201_4", title="Recurrence Relations & Generating Functions"),
                TopicItem(id="csl201_5", title="Graph Theory, Trees, and Eulerian/Hamiltonian Circuits")
            ]
        ),
        CourseDetail(
            code="CSL202",
            name="Data Structures",
            credits=4.0,
            ltp="3-0-2",
            aliases=["MAL504"],
            instructors=["Prof. Souradyuti Paul"],
            topics=[
                TopicItem(id="csl202_1", title="Asymptotic Analysis & Big-O Notation"),
                TopicItem(id="csl202_2", title="Arrays, Linked Lists, Stacks, and Queues"),
                TopicItem(id="csl202_3", title="Binary Search Trees, AVL Trees, and Red-Black Trees"),
                TopicItem(id="csl202_4", title="Priority Queues and Heaps"),
                TopicItem(id="csl202_5", title="Graph Traversal (BFS/DFS), Dijkstra, and MST"),
                TopicItem(id="csl202_6", title="Sorting and Searching Algorithms")
            ]
        ),
        CourseDetail(
            code="CSP203",
            name="Software Tools Lab",
            credits=2.0,
            ltp="0-0-4",
            aliases=[],
            instructors=["CS Faculty"],
            topics=[
                TopicItem(id="csp203_1", title="Unix Shell Scripting, awk, and sed"),
                TopicItem(id="csp203_2", title="Git Version Control & Branching Workflows"),
                TopicItem(id="csp203_3", title="Build Automation with Make and CMake"),
                TopicItem(id="csp203_4", title="Profiling, GDB Debugging, and Valgrind")
            ]
        ),
        CourseDetail(
            code="LAL100",
            name="Introduction to Communication Skills",
            credits=2.0,
            ltp="2-0-0",
            aliases=[],
            instructors=["Dr. Sruthi Vinayan"],
            topics=[
                TopicItem(id="lal100_1", title="Technical Report and Research Writing"),
                TopicItem(id="lal100_2", title="Academic Oral Presentations & Pitching"),
                TopicItem(id="lal100_3", title="Professional Email and Communication Etiquette")
            ]
        )
    ]

def reset_courses_to_default() -> None:
    """Resets dynamic course registry back to baseline defaults."""
    global _ACTIVE_COURSES_MAP
    _ACTIVE_COURSES_MAP = None

def get_active_courses() -> List[CourseDetail]:
    """
    Returns active course registry. If no timetable was uploaded to overwrite it,
    returns default baseline courses from Course of Study.
    """
    global _ACTIVE_COURSES_MAP
    if _ACTIVE_COURSES_MAP is None:
        return load_default_courses()
    return list(_ACTIVE_COURSES_MAP.values())

def get_course_by_code(code: str) -> Optional[CourseDetail]:
    courses = get_active_courses()
    code_upper = code.strip().upper()
    for c in courses:
        if c.code.upper() == code_upper or code_upper in [a.upper() for a in c.aliases]:
            return c
    return None

def sync_courses_from_timetable(timetable_slots: List[Any]) -> Dict[str, Any]:
    """
    Dynamically syncs course catalog from an uploaded Master Timetable:
    1. Starts with default Course of Study baseline.
    2. Overwrites instructors and aliases with live timetable data.
    3. Flags courses present in timetable as is_offered_this_sem = True.
    4. Flags remaining baseline courses as is_offered_this_sem = False.
    5. Dynamically registers brand-new courses found in timetable.
    """
    global _ACTIVE_COURSES_MAP
    
    # Initialize with fresh copy of baseline defaults
    baseline = load_default_courses()
    registry: Dict[str, CourseDetail] = {c.code.upper(): c for c in baseline}

    # By default, once a real timetable is uploaded, baseline courses start as not offered unless seen
    for c in registry.values():
        c.is_offered_this_sem = False

    new_courses_count = 0
    enriched_courses_count = 0

    for slot in timetable_slots:
        # slot can be ExamSlot object or dict
        courses_in_slot = slot.courses if hasattr(slot, "courses") else slot.get("courses", [])
        for c_entry in courses_in_slot:
            codes = c_entry.codes if hasattr(c_entry, "codes") else c_entry.get("codes", [])
            instructors = c_entry.instructors if hasattr(c_entry, "instructors") else c_entry.get("instructors", [])
            
            if not codes:
                continue

            primary_code = codes[0].strip().upper()
            all_aliases = [c.strip().upper() for c in codes]

            # Check if primary or any alias matches an existing baseline course
            matched_key = None
            for alias in all_aliases:
                if alias in registry:
                    matched_key = alias
                    break
                # Also check aliases field
                for k, v in registry.items():
                    if alias in [a.upper() for a in v.aliases]:
                        matched_key = k
                        break
                if matched_key:
                    break

            if matched_key:
                # Overwrite and enrich existing course
                target = registry[matched_key]
                target.is_offered_this_sem = True
                target.instructors = list(set(target.instructors + instructors))
                target.aliases = list(set(target.aliases + all_aliases))
                target.source = "Enriched"
                enriched_courses_count += 1
            else:
                # Brand new course offered this semester that wasn't in baseline Course of Study!
                new_course = CourseDetail(
                    code=primary_code,
                    name=f"{primary_code} (Active Timetable Offering)",
                    credits=3.0,
                    ltp="3-0-0",
                    prerequisites=[],
                    aliases=all_aliases,
                    instructors=instructors,
                    is_offered_this_sem=True,
                    source="MasterTimetable",
                    syllabus_raw="",
                    topics=[]
                )
                registry[primary_code] = new_course
                new_courses_count += 1

    _ACTIVE_COURSES_MAP = registry
    return {
        "status": "synchronized",
        "total_active_catalog": len(registry),
        "offered_this_semester": sum(1 for c in registry.values() if c.is_offered_this_sem),
        "enriched_baseline_courses": enriched_courses_count,
        "newly_discovered_courses": new_courses_count
    }

def load_curriculum() -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, "curriculum.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_semester_courses(branch: str, semester: str, only_offered: bool = False) -> Dict[str, Any]:
    curriculum = load_curriculum()
    branch_data = curriculum.get(branch.upper(), {})
    semesters = branch_data.get("semesters", {})
    sem_info = semesters.get(str(semester), {})
    
    course_codes = sem_info.get("courses", [])
    courses_details = []
    for c_code in course_codes:
        c_detail = get_course_by_code(c_code)
        if c_detail:
            if not only_offered or c_detail.is_offered_this_sem:
                courses_details.append(c_detail.model_dump())
        else:
            if not only_offered:
                courses_details.append({
                    "code": c_code,
                    "name": c_code,
                    "credits": 4.0,
                    "is_offered_this_sem": True,
                    "topics": []
                })

    return {
        "branch": branch.upper(),
        "branch_name": branch_data.get("name", branch),
        "semester": semester,
        "credits": sem_info.get("credits", 0),
        "default_courses": courses_details,
        "available_electives": sem_info.get("electives", [])
    }
