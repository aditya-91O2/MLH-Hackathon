---
name: campus-exam-prep-agent
description: Personalized Exam Preparation Agent for university students powered by Gemma 4. Ingests master timetables and course curricula to generate personalized exam schedules, topic-wise study plans, curated resources, and provides grounded doubt clearing.
version: 1.0.0
---

# Campus Exam Preparation Agent (`campus-exam-prep-agent`)

## Overview
An AI-powered academic copilot tailored for campus students. By combining official institute master timetables with the BTech Course of Study curriculum, the agent creates personalized study roadmaps, identifies exam slot clashes, curates learning materials (prioritizing NPTEL lectures), and answers student doubts with strict grounding.

## Agent Capabilities
1. **Curriculum & Timetable Structuring**: Parses complex, jumbled examination hall allocation PDFs and multi-page course structures into normalized schemas.
2. **Personalized Exam Scheduling**: Reconciles a student's enrolled courses with institute exam slots, cross-listing aliases (e.g. `CSL201/MAL503`), and highlights tight preparation windows.
3. **Adaptive Study Planning**: Uses Gemma 4 to formulate daily topic breakdowns factoring in course credits, topic difficulty, and buffer days prior to each exam.
4. **Material Curation & Gap Detection**: Matches lecture slides and book chapters to syllabus topics, discovering missing topics and querying external resources.
5. **Context-Aware Doubt Resolution**: Grounds Q&A in the student's actual course syllabus and lecture materials, citing specific sections and suggesting NPTEL video timestamps.

## Inputs
- **Branch & Semester**: e.g., `Computer Science & Engineering (CSE)`, `Semester III`.
- **Enrolled Course Codes**: Selected list of active courses and electives.
- **Syllabus Scope**: Checklists marking in-scope vs. excluded topics for upcoming mid-sem/end-sem exams.
- **Reference Documents**: Course description PDFs, master exam timetable JSON/PDF, uploaded lecture notes.

## Outputs
- **Personalized Exam Timetable**: Schedule with verified dates, times, halls, invigilators, and clash alerts.
- **Day-by-Day Study Plan**: Hourly allocations, revision checkpoints, and pre-exam buffers.
- **Curated Resource Index**: Topic-to-slide mappings and curated NPTEL / web links.
- **RAG Chat Responses**: Grounded answers citing course materials without hallucinations.

## Tool Definitions
- `get_exam_schedule(profile_id)`: Fetches exam dates and assigned halls for a student profile.
- `generate_study_plan(courses, exam_dates, start_date)`: Synthesizes a credit-weighted, balanced study plan.
- `search_youtube(query, prefer="NPTEL")`: Discovers high-quality video lectures prioritizing official academic channels.
- `web_search(query)`: Finds open-source textbooks and tutorials for topics without uploaded notes.
- `query_course_rag(course_code, query)`: Answers technical questions using syllabus and uploaded lecture chunks.
