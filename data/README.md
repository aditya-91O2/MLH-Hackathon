# Data Catalog Specification

This directory stores the baseline academic data for the Campus Exam Preparation Agent.

## Files

1. **`courses.json`**:
   - Baseline course descriptions extracted from the official BTech Course of Study.
   - Contains course codes, names, credits (L-T-P-C), prerequisites, raw syllabus paragraphs, and decomposed topics with subtopics.

2. **`curriculum.json`**:
   - Semester-wise mapping of core courses and available electives per discipline (CSE, DSAI, EE).

3. **`timetable.json`**:
   - Reference/fallback master timetable extracted from the institute examination schedule.
   - **Important:** The active timetable is dynamically loaded via `POST /api/timetable/upload` at runtime when a student or administrator uploads the session schedule. Uploaded timetables automatically synchronize active course offerings and instructor assignments.
