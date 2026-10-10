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
except (ImportError, ValueError):
    from ..parsers.curriculum_parser import (
        get_semester_courses,
        get_course_by_code,
        get_active_courses,
        load_default_courses,
        CourseDetail,
        TopicItem
    )


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
