import io
import re
import urllib.parse
import zipfile
import logging
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel

try:
    from rag import VectorStore, normalize_course_code
except (ImportError, ValueError):
    from ..rag import VectorStore, normalize_course_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/materials", tags=["Materials Curation"])

# Store metadata about uploaded files per course in memory
# { "default_user:CSL202": ["lecture1.pdf", "syllabus.pptx"] }
_USER_COURSE_FILES: Dict[str, List[str]] = {}


class CurateMaterialsRequest(BaseModel):
    courses: Optional[List[Any]] = []
    topics: Optional[List[Any]] = []
    uploaded_files: Optional[List[str]] = []
    user_id: Optional[str] = "default_user"


def extract_chunks_from_pdf(file_bytes: bytes, filename: str, course_code: str) -> List[Dict[str, Any]]:
    """Extract page-by-page text chunks from PDF using pypdf/pdfplumber."""
    chunks = []
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page_idx, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            paras = [p.strip() for p in text.split("\n\n") if p.strip()]
            current_chunk = ""
            chunk_subidx = 1
            for p in paras:
                if len(current_chunk) + len(p) > 700:
                    if current_chunk.strip():
                        chunks.append({
                            "id": f"{course_code}_{filename}_p{page_idx}_c{chunk_subidx}",
                            "text": current_chunk.strip(),
                            "source": f"{filename} (Page/Slide {page_idx})",
                            "page": str(page_idx),
                        })
                        chunk_subidx += 1
                    current_chunk = p + "\n"
                else:
                    current_chunk += p + "\n"
            if current_chunk.strip():
                chunks.append({
                    "id": f"{course_code}_{filename}_p{page_idx}_c{chunk_subidx}",
                    "text": current_chunk.strip(),
                    "source": f"{filename} (Page/Slide {page_idx})",
                    "page": str(page_idx),
                })
    except Exception as e:
        logger.warning(f"pypdf extraction error on {filename}: {e}")
        # Fallback to pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages, 1):
                    text = (page.extract_text() or "").strip()
                    if text:
                        chunks.append({
                            "id": f"{course_code}_{filename}_p{page_idx}",
                            "text": text,
                            "source": f"{filename} (Page {page_idx})",
                            "page": str(page_idx),
                        })
        except Exception as e2:
            logger.error(f"Failed to parse PDF {filename}: {e2}")
    return chunks


def extract_chunks_from_pptx(file_bytes: bytes, filename: str, course_code: str) -> List[Dict[str, Any]]:
    """Extract slide text from PPTX XML archives."""
    chunks = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            slide_files = [f for f in z.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")]
            slide_files.sort(key=lambda s: int(re.search(r'\d+', s).group()) if re.search(r'\d+', s) else 0)
            for idx, sfile in enumerate(slide_files, 1):
                xml_content = z.read(sfile)
                root = ET.fromstring(xml_content)
                texts = [node.text for node in root.iter() if node.text]
                slide_text = " ".join(texts).strip()
                if slide_text:
                    chunks.append({
                        "id": f"{course_code}_{filename}_slide{idx}",
                        "text": slide_text,
                        "source": f"{filename} (Slide {idx})",
                        "page": str(idx),
                    })
    except Exception as e:
        logger.warning(f"Failed to parse pptx {filename}: {e}")
    return chunks


def extract_chunks_from_text(file_bytes: bytes, filename: str, course_code: str) -> List[Dict[str, Any]]:
    """Extract paragraph chunks from text or markdown notes."""
    chunks = []
    text = file_bytes.decode("utf-8", errors="ignore").strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    for idx, p in enumerate(paras, 1):
        if len(p) > 20:
            chunks.append({
                "id": f"{course_code}_{filename}_p{idx}",
                "text": p,
                "source": f"{filename}",
                "page": str(idx),
            })
    return chunks


@router.post("/upload", summary="Upload slides/notes per course and ingest directly into RAG VectorStore")
async def upload_course_materials(
    course_code: str = Form(...),
    user_id: str = Form("default_user"),
    files: List[UploadFile] = File(...)
):
    """
    Parses uploaded syllabus/slide files (PDF, PPTX, TXT) and indexes them
    into the ChromaDB vector collection for the specified user and course.
    """
    canonical_code = normalize_course_code(course_code)
    all_chunks = []
    file_names = []

    for f in files:
        file_names.append(f.filename)
        contents = await f.read()
        lower_name = f.filename.lower()

        if lower_name.endswith(".pdf"):
            chunks = extract_chunks_from_pdf(contents, f.filename, canonical_code)
        elif lower_name.endswith((".pptx", ".ppt")):
            chunks = extract_chunks_from_pptx(contents, f.filename, canonical_code)
        else:
            chunks = extract_chunks_from_text(contents, f.filename, canonical_code)

        all_chunks.extend(chunks)

    # Ingest into VectorStore
    vs = VectorStore()
    if all_chunks:
        vs.add_chunks(user_id=user_id, course_code=canonical_code, chunks=all_chunks)

    # Record files uploaded
    store_key = f"{user_id}:{canonical_code}"
    existing = _USER_COURSE_FILES.get(store_key, [])
    for fn in file_names:
        if fn not in existing:
            existing.append(fn)
    _USER_COURSE_FILES[store_key] = existing

    return {
        "success": True,
        "course_code": canonical_code,
        "files_uploaded": file_names,
        "total_chunks_indexed": len(all_chunks),
        "message": f"Successfully indexed {len(all_chunks)} chunks from {len(file_names)} file(s) for {canonical_code} into RAG."
    }


def search_youtube_nptel(query: str, prefer_nptel: bool = True, max_results: int = 2) -> List[Dict[str, str]]:
    """
    Scrapes YouTube search to retrieve authentic NPTEL & educational university video lectures.
    Prioritizes verified NPTEL (IIT/IISc/SWAYAM) channels.
    Does not depend on broken youtubesearchpython library.
    """
    import requests
    import json
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    search_q = f"NPTEL {query}" if prefer_nptel else query
    encoded = urllib.parse.quote_plus(search_q)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    try:
        r = requests.get(url, headers=headers, timeout=7)
        match = re.search(r'var ytInitialData = ({.*?});</script>', r.text)
        if match:
            data = json.loads(match.group(1))
            videos = []

            def find_vr(obj):
                if isinstance(obj, dict):
                    if "videoRenderer" in obj:
                        vr = obj["videoRenderer"]
                        title = vr.get("title", {}).get("runs", [{}])[0].get("text", "")
                        vid = vr.get("videoId", "")
                        channel = vr.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
                        if vid and title:
                            is_nptel = any(k in channel.lower() or k in title.lower() for k in ["nptel", "iit", "swayam", "iisc", "nptelhrd"])
                            platform = "NPTEL" if is_nptel else "YouTube"
                            videos.append({
                                "title": title,
                                "channel": channel,
                                "url": f"https://www.youtube.com/watch?v={vid}",
                                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                                "platform": platform
                            })
                    for v in obj.values():
                        find_vr(v)
                elif isinstance(obj, list):
                    for item in obj:
                        find_vr(item)

            find_vr(data)
            if videos:
                nptel_vids = [v for v in videos if v["platform"] == "NPTEL"]
                other_vids = [v for v in videos if v["platform"] != "NPTEL"]
                return (nptel_vids + other_vids)[:max_results]
    except Exception as e:
        logger.warning(f"Error querying YouTube for '{query}': {e}")

    # Topic-specific verified search link fallback (never generic Graph Traversals)
    return [
        {
            "title": f"NPTEL Official Video Lecture Series: {query}",
            "channel": "NPTEL-IIT Official Channel",
            "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus('NPTEL ' + query)}",
            "thumbnail": "https://img.youtube.com/vi/default/hqdefault.jpg",
            "platform": "NPTEL"
        }
    ]


def get_web_study_resources(course: str, topic: str) -> List[Dict[str, str]]:
    """
    Generates direct authoritative academic web links for topics without uploaded notes.
    Combines NPTEL Portal, MIT OCW / Stanford notes, and GeeksforGeeks / LibreTexts.
    """
    encoded_topic = urllib.parse.quote_plus(topic)
    encoded_course_topic = urllib.parse.quote_plus(f"{course} {topic} tutorial notes solved examples")

    return [
        {
            "title": f"NPTEL / SWAYAM Portal: {course} - {topic}",
            "source": "NPTEL National Portal",
            "type": "Course Transcripts, Slides & Assignments",
            "url": f"https://nptel.ac.in/courses?search={encoded_topic}",
            "topic": topic
        },
        {
            "title": f"{topic} — Comprehensive Tutorial, Proofs & Solved Problems",
            "source": "Academic Notes & Problem Sets",
            "type": "Tutorial & Practice",
            "url": f"https://www.google.com/search?q={encoded_course_topic}",
            "topic": topic
        },
        {
            "title": f"MIT OpenCourseWare / Stanford Lecture Notes: {topic}",
            "source": "OpenCourseWare Repository",
            "type": "Reference Notes & Lecture Slides",
            "url": f"https://ocw.mit.edu/search/?q={encoded_topic}",
            "topic": topic
        }
    ]


@router.post("/curate", summary="Curate NPTEL, YouTube, and web study materials for enrolled topics")
def curate_materials(req: CurateMaterialsRequest):
    """
    Materials Curation:
    - Prioritizes authentic NPTEL & educational video lectures matched to selected topics.
    - Shows uploaded files per course.
    - Searches the web for authoritative text notes, open textbooks, and problem sets for uncovered topics.
    - Generates a syllabus coverage table.
    """
    videos_result = []
    web_resources = []
    coverage_table = []
    seen_urls = set()
    user_id = req.user_id or "default_user"

    # Identify courses and their uploaded materials
    course_materials_status = {}
    if req.courses:
        for c in req.courses:
            code = c.get("code", "") if isinstance(c, dict) else str(c)
            canonical = normalize_course_code(code)
            key = f"{user_id}:{canonical}"
            uploaded = _USER_COURSE_FILES.get(key, [])
            course_materials_status[canonical] = uploaded

    # Collect topics
    topic_items = []
    if req.topics:
        for t in req.topics:
            if isinstance(t, dict):
                course = t.get("course", "")
                topic_name = t.get("topic", "")
                if topic_name:
                    topic_items.append({"course": course, "topic": topic_name})
            elif isinstance(t, str):
                topic_items.append({"course": "Core Track", "topic": t})
    elif req.courses:
        for c in req.courses:
            name = c.get("name", c.get("code", "")) if isinstance(c, dict) else str(c)
            topic_items.append({"course": name, "topic": "Key Concepts & Problem Sets"})

    if not topic_items:
        topic_items = [
            {"course": "Core Track", "topic": "Core Foundations & Proofs"},
            {"course": "Core Track", "topic": "Problem Sets & Revision"}
        ]

    # Fetch targeted NPTEL videos and web notes for each topic
    for item in topic_items[:6]:
        course = item["course"]
        topic = item["topic"]
        canonical = normalize_course_code(course.split()[0])
        uploaded_files = course_materials_status.get(canonical, [])
        has_uploaded_notes = len(uploaded_files) > 0

        # 1. Fetch authentic NPTEL / YouTube lectures
        vids = search_youtube_nptel(f"{course} {topic}", prefer_nptel=True, max_results=2)
        for v in vids:
            u = v.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                videos_result.append({
                    "title": v.get("title", f"{course}: {topic}"),
                    "channel": v.get("channel", "NPTEL-IIT Official"),
                    "url": u,
                    "thumbnail": v.get("thumbnail", ""),
                    "platform": v.get("platform", "NPTEL"),
                    "course": course,
                    "topic": topic
                })

        # 2. Generate authoritative academic web resources
        web_links = get_web_study_resources(course, topic)
        web_resources.extend(web_links)

        # 3. Add to coverage table
        coverage_table.append({
            "course": course,
            "topic": topic,
            "status": "Covered via Uploaded Slides & NPTEL" if has_uploaded_notes else "Covered via Curated NPTEL & Web Notes",
            "has_uploaded_notes": has_uploaded_notes,
            "uploaded_files": uploaded_files,
            "external_links_attached": len(web_links)
        })

    return {
        "reply": f"I've analyzed your course scope and curated top NPTEL IIT video lectures, open academic textbooks, and tutorial problem sets for your {len(topic_items)} selected topic(s).",
        "videos": videos_result[:6],
        "web_resources": web_resources[:6],
        "coverage_table": coverage_table,
        "course_materials": course_materials_status
    }
