# Hackathon Presentation Slides Outline (PPT)
> **Track:** Build for Your Campus | **MLH Awards:** Best Use of Gemma 4, Best Open Source AI Project

---

### Slide 1: Title & Team
- **Title:** Personalized Campus Exam Preparation Agent
- **Subtitle:** Transforming Raw University Timetables and Curricula into Adaptive Student Roadmaps with Gemma 4
- **Team Name & Members**
- **Repository Link:** Public GitHub Repo

---

### Slide 2: The Campus Problem
- **The Chaos of University Exam Week:**
  - Multi-page jumbled master timetable PDFs with 50+ slots, interleaved rooms, and cross-listed codes (`CSL201/MAL503`).
  - Massive course-of-study curriculum documents where only a fraction of courses run in any given semester.
  - Zero personalized guidance: students manually search for their halls, often miss tight exam gaps (< 24 hrs), and struggle to balance prep across 4-credit vs 2-credit subjects.

---

### Slide 3: Our Solution
- **An End-to-End Autonomous Academic Copilot:**
  - **Dynamic Ingestion:** Upload any exam timetable PDF -> instant parsing of slots, split halls, and instructors.
  - **Personal Schedule Reconciler:** Instant mapping of student's enrolled courses with automatic alias resolution.
  - **Clash & Tight Gap Alerts:** Flags exam conflicts and back-to-back testing pressures in advance.
  - **Adaptive Study Planner:** Credit-weighted hourly allocations with mandatory pre-exam revision buffers.

---

### Slide 4: Role of Gemma 4
- **Pedagogical Reasoning & Structure:**
  - Dissects multi-tier syllabi into ordered subtopics with estimated cognitive loads.
  - Formulates day-by-day revision strategies balancing difficult subjects (e.g. Data Structures vs Lab courses).
  - Division of Responsibility: Plain Python handles strict date arithmetic & credit math; Gemma 4 handles semantic understanding, topic decomposition, and pedagogical planning.

---

### Slide 5: System Architecture
- *Include Mermaid Architecture Diagram from docs/ARCHITECTURE.md*
- FastAPI high-performance asynchronous backend.
- Dynamic in-memory catalogue synchronization (overwriting instructor/course availability on timetable upload).

---

### Slide 6: Live Demo Walkthrough
1. **Dynamic Master Timetable Upload:** `POST /api/timetable/upload` parses real IIT Bhilai exam schedule.
2. **Personal Timetable Generation:** Student enters `["MAL403", "CSL201", "CSL202", "CSP203", "LAL100"]`.
3. **Hazard Detection:** Flags tight gap (< 21 hours) between CSL202 and LAL100.
4. **Adaptive Study Plan Generation:** `POST /api/plan/generate` produces balanced schedule with pre-exam buffers.

---

### Slide 7: Real-World Impact & Campus Scalability
- Directly usable by any university student or academic section.
- Open-source, modular, and readily extensible to any university curriculum format.
- MIT Licensed.
