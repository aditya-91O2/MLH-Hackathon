/**
 * Frontend API Client
 * Connects UI seamlessly to the FastAPI backend and Gemma 4 Agent.
 */

// Resolve backend API URL dynamically:
// - If loaded via HTTP/HTTPS from backend (e.g. port 8080, 8000), use relative URL ''
// - If loaded via Live Server (5500) or file://, target http://localhost:8080
const API_BASE = (() => {
    if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
        if (window.location.port !== '5500' && window.location.port !== '5173') {
            return '';
        }
        return `http://${window.location.hostname || 'localhost'}:8080`;
    }
    return 'http://localhost:8080';
})();

const apiClient = {
    /**
     * Uploads the student's timetable PDF or Image to the backend.
     * @param {File} file 
     * @returns {Promise<Object>} { reply, extracted_data: { courses, study_hours, start_date } }
     */
    async uploadTimetable(file) {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${API_BASE}/api/timetable/upload`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || err.error || `HTTP Error ${res.status}`);
        }

        return await res.json();
    },

    /**
     * Fetches syllabus topics for confirmed enrolled courses.
     * @param {Array} courses 
     * @returns {Promise<Object>} { reply, topics: [{ course, code, topic, included }] }
     */
    async fetchTopics(courses) {
        const res = await fetch(`${API_BASE}/api/courses/topics`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ courses })
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || `HTTP Error ${res.status}`);
        }

        return await res.json();
    },

    /**
     * Uploads course slides / notes for RAG vector indexing.
     * @param {string} courseCode
     * @param {FileList|Array<File>} files
     * @returns {Promise<Object>} { success, total_chunks_indexed, files_uploaded }
     */
    async uploadMaterials(courseCode, files) {
        const formData = new FormData();
        formData.append('course_code', courseCode);
        formData.append('user_id', 'default_user');
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        const res = await fetch(`${API_BASE}/api/materials/upload`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || err.error || `HTTP Error ${res.status}`);
        }

        return await res.json();
    },

    /**
     * Curates authentic NPTEL/YouTube video lectures and academic web study materials and problem sets.
     * @param {Object} payload { courses, topics }
     * @returns {Promise<Object>} { reply, videos: [...], web_resources: [...], coverage_table: [...] }
     */
    async curateMaterials(payload) {
        const res = await fetch(`${API_BASE}/api/materials/curate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || `HTTP Error ${res.status}`);
        }

        return await res.json();
    },

    /**
     * Synthesizes credit-weighted study roadmap with buffer days.
     * @param {Object} payload { courses, constraints, daily_hours, start_date }
     * @returns {Promise<Object>} { reply, study_plan: [...] }
     */
    async generateRoadmap(payload) {
        const res = await fetch(`${API_BASE}/api/plan/roadmap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || `HTTP Error ${res.status}`);
        }

        return await res.json();
    },

    /**
     * Chatbot query endpoint (Under construction).
     * @param {Object} payload { course_code, message, history, enrolled_courses }
     * @returns {Promise<Object>} { reply, answer }
     */
    async sendChat(payload) {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            let err = {};
            try { err = await res.json(); } catch(e) {}
            throw new Error(err.detail || `HTTP Error ${res.status}`);
        }

        return await res.json();
    }
};
