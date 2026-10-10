import io
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class HallAllocation(BaseModel):
    hall: str
    assigned: int
    invigilator: Optional[str] = None

class CourseExamEntry(BaseModel):
    codes: List[str]
    instructors: List[str] = []
    students: int = 0
    halls: List[HallAllocation] = []

class ExamSlot(BaseModel):
    slot_no: int
    date: str  # YYYY-MM-DD
    start: str # HH:MM
    end: str   # HH:MM
    total_students: Optional[int] = None
    courses: List[CourseExamEntry] = []

class MasterTimetable(BaseModel):
    exam_type: str = "MidSem"
    session: str = "2026-27"
    slots: List[ExamSlot] = []

class PersonalExamItem(BaseModel):
    course_code: str
    matched_alias: str
    slot_no: int
    date: str
    start: str
    end: str
    instructors: List[str]
    students: int
    halls: List[HallAllocation]
    clashes_with: List[str] = []
    tight_gap_warning: Optional[str] = None

class PersonalTimetableResponse(BaseModel):
    schedule: List[PersonalExamItem]
    has_clashes: bool
    clash_details: List[str]
    tight_gaps: List[str]
    unmatched_courses: List[str]

# Global in-memory storage for active uploaded timetable
_ACTIVE_TIMETABLE: Optional[MasterTimetable] = None

def get_active_timetable() -> Optional[MasterTimetable]:
    return _ACTIVE_TIMETABLE

def set_active_timetable(timetable: Optional[MasterTimetable]) -> None:
    global _ACTIVE_TIMETABLE
    _ACTIVE_TIMETABLE = timetable

def parse_timetable_text(raw_text: str) -> MasterTimetable:
    """
    Parses extracted text from exam timetable PDF.
    Extracts slots, dates, course codes (handling '/' aliases) and hall allocations.
    """
    timetable = MasterTimetable()
    
    # Slot header pattern: e.g. "21 21 September 2026 10:30 AM to 12:30 PM 892"
    slot_pattern = re.compile(
        r'(\d{1,2})\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(\d{1,2}:\d{2}\s*(?:AM|PM))\s+to\s+(\d{1,2}:\d{2}\s*(?:AM|PM))\s+(\d+)?',
        re.IGNORECASE
    )
    
    matches = list(slot_pattern.finditer(raw_text))
    if not matches:
        return timetable

    for i, match in enumerate(matches):
        slot_no = int(match.group(1))
        date_str_raw = match.group(2)
        start_time_raw = match.group(3)
        end_time_raw = match.group(4)
        total_students = int(match.group(5)) if match.group(5) else None

        try:
            parsed_date = datetime.strptime(date_str_raw, "%d %B %Y").strftime("%Y-%m-%d")
        except Exception:
            parsed_date = date_str_raw

        try:
            start_fmt = datetime.strptime(start_time_raw.replace(" ", ""), "%I:%M%p").strftime("%H:%M")
            end_fmt = datetime.strptime(end_time_raw.replace(" ", ""), "%I:%M%p").strftime("%H:%M")
        except Exception:
            start_fmt = start_time_raw
            end_fmt = end_time_raw

        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        slot_block = raw_text[start_pos:end_pos]

        slot = ExamSlot(
            slot_no=slot_no,
            date=parsed_date,
            start=start_fmt,
            end=end_fmt,
            total_students=total_students,
            courses=[]
        )

        course_line_pattern = re.compile(
            r'(\d+)?\s*([A-Z]{2,3}\d{3}(?:/[A-Z0-9]+)*)\s+([^0-9\n]+?)\s+(\d+)\s+([A-Z0-9\-\s/]+?)\s+([A-Za-z\.\s]+)',
            re.MULTILINE
        )

        for cm in course_line_pattern.finditer(slot_block):
            c_code_raw = cm.group(2).strip()
            instructor = cm.group(3).strip()
            assigned = int(cm.group(4))
            hall = cm.group(5).strip()
            invigilator = cm.group(6).strip()
            
            codes = [c.strip() for c in c_code_raw.split("/")]
            
            existing = next((c for c in slot.courses if set(c.codes) == set(codes)), None)
            if existing:
                existing.halls.append(HallAllocation(hall=hall, assigned=assigned, invigilator=invigilator))
                existing.students += assigned
            else:
                slot.courses.append(CourseExamEntry(
                    codes=codes,
                    instructors=[instructor] if instructor else [],
                    students=assigned,
                    halls=[HallAllocation(hall=hall, assigned=assigned, invigilator=invigilator)]
                ))

        timetable.slots.append(slot)

    return timetable

def parse_timetable_pdf(file_bytes: bytes) -> MasterTimetable:
    """Extracts text from PDF and parses it into MasterTimetable."""
    try:
        import pdfplumber
        full_text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        return parse_timetable_text(full_text)
    except ImportError:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
        return parse_timetable_text(full_text)

def generate_personal_schedule(
    enrolled_courses: List[str],
    timetable: MasterTimetable
) -> PersonalTimetableResponse:
    """
    Joins enrolled courses with the timetable:
    - Matches any cross-listed alias (e.g. CSL201 matches CSL201/MAL503)
    - Detects slot clashes (multiple exams in same slot/time)
    - Detects tight gaps (< 24 hours between consecutive exams)
    """
    schedule: List[PersonalExamItem] = []
    unmatched: List[str] = []

    for course_code in enrolled_courses:
        norm_course = course_code.strip().upper()
        matched = False

        for slot in timetable.slots:
            for c_entry in slot.courses:
                entry_codes = [c.upper() for c in c_entry.codes]
                if norm_course in entry_codes:
                    item = PersonalExamItem(
                        course_code=norm_course,
                        matched_alias="/".join(c_entry.codes),
                        slot_no=slot.slot_no,
                        date=slot.date,
                        start=slot.start,
                        end=slot.end,
                        instructors=c_entry.instructors,
                        students=c_entry.students,
                        halls=c_entry.halls
                    )
                    schedule.append(item)
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            unmatched.append(norm_course)

    schedule.sort(key=lambda x: f"{x.date} {x.start}")

    # Detect clashes
    clashes: List[str] = []
    slot_map: Dict[int, List[PersonalExamItem]] = {}
    for item in schedule:
        slot_map.setdefault(item.slot_no, []).append(item)

    for slot_no, items in slot_map.items():
        if len(items) > 1:
            clashing_codes = [i.course_code for i in items]
            msg = f"Slot {slot_no} Clash on {items[0].date}: " + " vs ".join(clashing_codes)
            clashes.append(msg)
            for i in items:
                i.clashes_with = [c for c in clashing_codes if c != i.course_code]

    # Detect tight gaps
    tight_gaps: List[str] = []
    for idx in range(len(schedule) - 1):
        curr_exam = schedule[idx]
        next_exam = schedule[idx + 1]
        try:
            curr_dt = datetime.strptime(f"{curr_exam.date} {curr_exam.end}", "%Y-%m-%d %H:%M")
            next_dt = datetime.strptime(f"{next_exam.date} {next_exam.start}", "%Y-%m-%d %H:%M")
            diff_hours = (next_dt - curr_dt).total_seconds() / 3600.0
            if diff_hours < 24.0 and diff_hours > 0:
                warning_msg = f"Tight gap ({diff_hours:.1f} hrs) between {curr_exam.course_code} and {next_exam.course_code}"
                tight_gaps.append(warning_msg)
                next_exam.tight_gap_warning = warning_msg
        except Exception:
            pass

    return PersonalTimetableResponse(
        schedule=schedule,
        has_clashes=len(clashes) > 0,
        clash_details=clashes,
        tight_gaps=tight_gaps,
        unmatched_courses=unmatched
    )
