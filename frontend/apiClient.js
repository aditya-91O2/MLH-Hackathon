/**
 * Frontend API Client
 * Connects UI seamlessly to the FastAPI backend and Gemma 4 Agent.
 */

// If served together from FastAPI, relative path is used.
// If served from a separate server, fallback to localhost:8000.
const API_BASE = window.location.port === '8000' || window.location.port === '3000'
    ? ''
    : 'http://localhost:8000';

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
     * Curates NPTEL and YouTube lecture videos for active topics.
     * @param {Object} payload { courses, topics }
     * @returns {Promise<Object>} { reply, videos: [{ title, platform, url }] }
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
     * Course-aware doubt clearing chatbot query.
     * @param {Object} payload { course_code, message, history, enrolled_courses }
     * @returns {Promise<Object>} { reply, answer, citations, video_recommendations }
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
