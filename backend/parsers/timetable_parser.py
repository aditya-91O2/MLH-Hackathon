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
    credits: Optional[float] = None
    ltp: Optional[str] = None

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
    credits: Optional[float] = None

class PersonalTimetableResponse(BaseModel):
    schedule: List[PersonalExamItem]
    has_clashes: bool
    clash_details: List[str]
    tight_gaps: List[str]
    unmatched_courses: List[str]

# Global in-memory storage for active uploaded timetable
_ACTIVE_TIMETABLE: Optional[MasterTimetable] = None

def get_active_timetable() -> Optional[MasterTimetable]:
    global _ACTIVE_TIMETABLE
    if _ACTIVE_TIMETABLE is not None:
        return _ACTIVE_TIMETABLE
    import os, json
    # 1. Try active_timetable.json
    active_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "active_timetable.json")
    if os.path.exists(active_path):
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _ACTIVE_TIMETABLE = MasterTimetable.model_validate(data)
                return _ACTIVE_TIMETABLE
        except Exception:
            pass
    # 2. Try default timetable.json
    tt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "timetable.json")
    if os.path.exists(tt_path):
        try:
            with open(tt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _ACTIVE_TIMETABLE = MasterTimetable.model_validate(data)
                return _ACTIVE_TIMETABLE
        except Exception:
            pass
    return None

def set_active_timetable(timetable: Optional[MasterTimetable]) -> None:
    global _ACTIVE_TIMETABLE
    _ACTIVE_TIMETABLE = timetable
    import os, json
    active_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "active_timetable.json")
    if timetable is not None:
        try:
            os.makedirs(os.path.dirname(active_path), exist_ok=True)
            with open(active_path, "w", encoding="utf-8") as f:
                json.dump(timetable.model_dump(), f, indent=2)
        except Exception:
            pass
    else:
        if os.path.exists(active_path):
            try:
                os.remove(active_path)
            except Exception:
                pass

def extract_credit_from_text(text: str) -> Optional[float]:
    """Extracts credits or LTP specification from timetable text."""
    if not text:
        return None
    # 1. Matches "4 credits", "Credits: 4", "3.5 cr"
    cr_match = re.search(r'(?:credits?|cr\.?)\s*[:=\s]\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if cr_match:
        try:
            return float(cr_match.group(1))
        except Exception:
            pass
    # 2. Matches "4.0 credits" or "4 credits"
    cr_match2 = re.search(r'\b([1-6](?:\.[05])?)\s*(?:credits?|cr\b)', text, re.IGNORECASE)
    if cr_match2:
        try:
            return float(cr_match2.group(1))
        except Exception:
            pass
    # 3. Matches LTP format "3-1-0" or "(3-0-2)" -> credits = L + T + P/2.0
    ltp_match = re.search(r'(?:ltp[:=\s]*)?\(?(\d+)[-\s](\d+)[-\s](\d+)\)?', text, re.IGNORECASE)
    if ltp_match:
        try:
            l = int(ltp_match.group(1))
            t = int(ltp_match.group(2))
            p = int(ltp_match.group(3))
            return float(l + t + (p / 2.0))
        except Exception:
            pass
    return None

def resolve_course_credits(course_code: str, timetable: Optional[MasterTimetable] = None) -> float:
    """
    Extracts course credit weight directly from active master timetable slots or metadata.
    Falls back to active curriculum catalog, then course code structure heuristics.
    """
    code_upper = course_code.strip().upper()

    # 1. Inspect timetable slots for explicit credit declaration
    if timetable:
        for slot in timetable.slots:
            for c in slot.courses:
                for c_code in c.codes:
                    if code_upper == c_code.upper() or code_upper in c_code.upper():
                        if c.credits and c.credits > 0:
                            return float(c.credits)

    # 2. Check active courses registry (curriculum_parser)
    try:
        from parsers.curriculum_parser import get_course_by_code
        c_obj = get_course_by_code(code_upper)
        if c_obj and c_obj.credits and c_obj.credits > 0:
            return float(c_obj.credits)
    except Exception:
        pass

    # 3. Intelligent heuristic from academic code convention:
    # Practical Lab courses (contains P e.g. CSP203, MEP101, CYP501, or contains 'LAB'): 2.0 credits
    if "LAB" in code_upper or re.search(r'^[A-Z]{2,3}P\d+', code_upper):
        return 2.0

    # 100 level / communication / general skills: 2.0 - 3.0 credits
    if re.search(r'^[A-Z]{2,3}[1]\d\d', code_upper):
        if code_upper.startswith("LA") or code_upper.startswith("HS"):
            return 2.0
        return 3.0

    # 200, 300, 400 core engineering & science / 600, 700 advanced electives: 4.0 credits
    return 4.0

def parse_flexible_timetable_text(raw_text: str) -> MasterTimetable:
    """
    Fallback parser for simple/unstructured formats like:
      Biology: 2026-11-20
      Chemistry: 2026-11-25
      CSL202 - 2026-09-24
    """
    timetable = MasterTimetable()
    lines = raw_text.splitlines()
    slot_no = 1
    
    flexible_pattern = re.compile(
        r'([A-Za-z0-9\s/&]+?)[:\-\t|]+\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})'
    )
    reverse_pattern = re.compile(
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})[:\-\t|]+\s*([A-Za-z0-9\s/&]+)'
    )

    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith("exam timetable") or line.lower().startswith("timetable"):
            continue
        
        course_name = None
        date_raw = None
        
        m = flexible_pattern.search(line)
        if m:
            course_name = m.group(1).strip()
            date_raw = m.group(2).strip()
        else:
            rm = reverse_pattern.search(line)
            if rm:
                date_raw = rm.group(1).strip()
                course_name = rm.group(2).strip()
        
        if course_name and date_raw:
            parsed_date = date_raw
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
                try:
                    parsed_date = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                    break
                except Exception:
                    pass
            
            clean_name = course_name.strip(" :-|")
            if clean_name:
                line_credit = extract_credit_from_text(line)
                slot = ExamSlot(
                    slot_no=slot_no,
                    date=parsed_date,
                    start="10:00",
                    end="13:00",
                    courses=[CourseExamEntry(
                        codes=[clean_name],
                        instructors=["Faculty"],
                        students=60,
                        halls=[HallAllocation(hall="L-209", assigned=60)],
                        credits=line_credit or resolve_course_credits(clean_name, timetable)
                    )]
                )
                timetable.slots.append(slot)
                slot_no += 1
                
    return timetable

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
        return parse_flexible_timetable_text(raw_text)

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
            matched_line_text = cm.group(0)
            line_credit = extract_credit_from_text(matched_line_text) or extract_credit_from_text(slot_block)
            course_credit = line_credit or resolve_course_credits(codes[0], timetable)

            existing = next((c for c in slot.courses if set(c.codes) == set(codes)), None)
            if existing:
                existing.halls.append(HallAllocation(hall=hall, assigned=assigned, invigilator=invigilator))
                existing.students += assigned
                if course_credit and not existing.credits:
                    existing.credits = course_credit
            else:
                slot.courses.append(CourseExamEntry(
                    codes=codes,
                    instructors=[instructor] if instructor else [],
                    students=assigned,
                    halls=[HallAllocation(hall=hall, assigned=assigned, invigilator=invigilator)],
                    credits=course_credit
                ))

        timetable.slots.append(slot)

    if not timetable.slots:
        return parse_flexible_timetable_text(raw_text)

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
    - Attaches credits extracted from master timetable
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
                        halls=c_entry.halls,
                        credits=c_entry.credits or resolve_course_credits(norm_course, timetable)
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

def get_default_master_timetable() -> MasterTimetable:
    """Returns baseline semester examination timetable with authentic credits."""
    sample_courses = [
        {"code": "MAL403", "name": "Probability and Statistics", "instructor": "Dr. Lakshmi Kanta Patra", "date": "2026-09-18", "slot_no": 11, "hall": "L-209", "credits": 4.0},
        {"code": "CYL609", "name": "Crystal Engineering & Supramolecular Materials", "instructor": "Dr. Prabal Banerjee", "date": "2026-09-18", "slot_no": 11, "hall": "L-209", "credits": 4.0},
        {"code": "CSL201", "name": "Discrete Mathematics", "instructor": "Dr. Rishi Ranjan Singh", "date": "2026-09-21", "slot_no": 21, "hall": "L-209", "credits": 4.0},
        {"code": "CSL605", "name": "Parallel and Distributed Computing", "instructor": "Dr. Subhasis Bhattacharjee", "date": "2026-09-22", "slot_no": 31, "hall": "L-209", "credits": 4.0},
        {"code": "CSP203", "name": "Software Tools Lab", "instructor": "CS Faculty", "date": "2026-09-23", "slot_no": 0, "hall": "Lab Session", "credits": 2.0},
        {"code": "CSL202", "name": "Data Structures", "instructor": "Prof. Souradyuti Paul", "date": "2026-09-24", "slot_no": 51, "hall": "L-209", "credits": 4.0},
        {"code": "LAL100", "name": "Introduction to Communication Skills", "instructor": "Dr. Sruthi Vinayan", "date": "2026-09-25", "slot_no": 61, "hall": "L-209", "credits": 2.0}
    ]
    tt = MasterTimetable(exam_type="MidSem", session="2026-27")
    for sc in sample_courses:
        slot = ExamSlot(
            slot_no=sc["slot_no"],
            date=sc["date"],
            start="10:30",
            end="12:30",
            courses=[CourseExamEntry(
                codes=[sc["code"]],
                instructors=[sc["instructor"]],
                students=80,
                halls=[HallAllocation(hall=sc["hall"], assigned=80)],
                credits=sc.get("credits", 4.0)
            )]
        )
        tt.slots.append(slot)
    return tt

