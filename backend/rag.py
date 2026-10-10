"""
Course-aware chatbot (RAG) module:
Context = syllabus topics + course materials + user's plan.
Gemma 4 grounded responses with citations.
Tool calling support for YouTube (prioritizing NPTEL).
"""

from typing import List, Dict, Any, Optional

def query_rag(
    course_code: str,
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Answers doubts with citations and recommended NPTEL/YouTube material."""
    return {
        "answer": f"Answer for {course_code}: {user_query}",
        "citations": [],
        "video_recommendations": []
    }
