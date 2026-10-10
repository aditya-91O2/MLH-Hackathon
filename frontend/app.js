document.addEventListener('DOMContentLoaded', () => {
    console.log("Study Planner - Live Backend & Gemma 4 Connected");
    initUI();
});

// State
let studyContext = {
    courses: [],
    study_hours: 4,
    start_date: null,
    selectedTopics: []
};
let chatHistory = [];

// DOM Elements
const chatHistoryEl = document.getElementById('chat-history');
const initialUpload = document.getElementById('initial-upload');
const chatComposer = document.getElementById('chat-composer');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe.toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;");
}

function updateContextSummary() {
    const activeCount = studyContext.courses.filter(c => c.selected !== false).length;
    document.getElementById('summary-course-count').textContent = activeCount;
    if (studyContext.study_hours) {
        document.getElementById('summary-study-hours').textContent = studyContext.study_hours;
    }
}

function initUI() {
    document.getElementById('toggle-context-btn').addEventListener('click', (e) => {
        const card = e.currentTarget.parentElement;
        card.classList.toggle('collapsed');
    });

    document.getElementById('reset-demo-btn').addEventListener('click', () => location.reload());

    // 1. Live Timetable Upload
    initialUpload.addEventListener('change', async (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            const uploadArea = document.getElementById('initial-upload-area');
            if (uploadArea) uploadArea.classList.add('hidden');
            
            appendMessage('user', `[Uploaded file: ${file.name}]`);
            chatComposer.classList.remove('hidden');
            
            const loadingId = 'loading-' + Date.now();
            appendMessage('assistant', `<span id="${loadingId}">Gemma 4 is parsing your timetable and extracting exam slots... ⏳</span>`);
            
            try {
                const extraction = await apiClient.uploadTimetable(file);
                
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.parentElement.parentElement.remove();
                
                showCourseReview(extraction);
            } catch (err) {
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.parentElement.parentElement.remove();
                appendMessage('assistant', `⚠️ Could not parse uploaded timetable: ${err.message}. Please check server connectivity.`);
            }
        }
    });

    // Chat submit
    chatSend.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSubmit();
        }
    });
}

// ----------------------------------------------------
// Live Chat / Doubt Clearing
// ----------------------------------------------------
async function handleChatSubmit() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    chatHistory.push({ role: 'user', content: text });
    chatInput.value = '';

    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Gemma 4 is analyzing your query... ⏳</span>`);

    // Determine primary active course
    const activeCourse = (studyContext.courses.find(c => c.selected !== false) || {}).code || "CSL202";
    const enrolledCodes = studyContext.courses.map(c => c.code).filter(Boolean);

    try {
        const res = await apiClient.sendChat({
            course_code: activeCourse,
            message: text,
            history: chatHistory.slice(-6),
            enrolled_courses: enrolledCodes
        });

        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();

        const answerText = res.answer || res.reply || "I've reviewed your question.";
        let formatted = escapeHtml(answerText).replace(/\n/g, '<br>');

        if (res.video_recommendations && res.video_recommendations.length > 0) {
            formatted += `<br><br><strong>Recommended NPTEL / Video Lectures:</strong><ul>`;
            res.video_recommendations.forEach(v => {
                formatted += `<li><a href="${escapeHtml(v.url)}" target="_blank">${escapeHtml(v.title)}</a> (${escapeHtml(v.channel || 'NPTEL')})</li>`;
            });
            formatted += `</ul>`;
        }

        appendMessage('assistant', formatted);
        chatHistory.push({ role: 'assistant', content: answerText });
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        appendMessage('assistant', `⚠️ Could not get AI response: ${err.message}`);
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = `<p>${text}</p>`;
    chatHistoryEl.appendChild(msgDiv);
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

function appendCustomCard(htmlString) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = htmlString;
    chatHistoryEl.appendChild(wrapper.firstElementChild);
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

// ----------------------------------------------------
// UI Flow: Step 1 - Course Review (Live Data)
// ----------------------------------------------------
function showCourseReview(extraction) {
    studyContext.courses = JSON.parse(JSON.stringify(extraction.extracted_data.courses || []));
    studyContext.study_hours = extraction.extracted_data.study_hours || 4;
    studyContext.start_date = extraction.extracted_data.start_date;
    updateContextSummary();

    appendMessage('assistant', escapeHtml(extraction.reply));
    
    let listHtml = '';
    studyContext.courses.forEach((course, index) => {
        listHtml += `
            <div class="selection-item">
                <div class="selection-left" style="align-items: flex-start;">
                    <input type="checkbox" id="course-${index}" class="selection-checkbox" checked style="margin-top: 4px;">
                    <label for="course-${index}">
                        <strong>${escapeHtml(course.code || '')}</strong>: ${escapeHtml(course.name || course.code)}
                        <span style="display:block; font-size:0.85rem; color:var(--text-muted); margin-top:4px;">
                            Instructor: ${escapeHtml(course.instructor || 'Faculty')} | Slot: ${escapeHtml(course.slot_no || '')} (${escapeHtml(course.hall || 'L-209')})
                        </span>
                    </label>
                </div>
                <div class="selection-right">
                    ${escapeHtml(course.exam_date || '')}
                </div>
            </div>
        `;
    });

    const cardId = 'course-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4>Extracted Examination Courses</h4>
            <div class="selection-list">
                ${listHtml}
            </div>
            <button class="btn btn-primary" onclick="confirmCourses('${cardId}')">Confirm Selection</button>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}

window.confirmCourses = async function(cardId) {
    const card = document.getElementById(cardId);
    if(card) {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if(btn) btn.textContent = "Confirmed ✓";
        
        const checkboxes = card.querySelectorAll('.selection-checkbox');
        checkboxes.forEach((cb, idx) => {
            if(studyContext.courses[idx]) {
                studyContext.courses[idx].selected = cb.checked;
            }
        });
        updateContextSummary();
    }
    
    appendMessage('user', "I have confirmed my course selection.");
    
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Gemma 4 is mapping curriculum topics and prerequisites... ⏳</span>`);
    
    try {
        const selectedCourses = studyContext.courses.filter(c => c.selected !== false);
        const topicsData = await apiClient.fetchTopics(selectedCourses);

        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        
        showTopicsAndResources(topicsData);
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        appendMessage('assistant', `⚠️ Could not fetch course topics: ${err.message}`);
    }
}

// ----------------------------------------------------
// UI Flow: Step 2 - Topics & Materials Request (Live Data)
// ----------------------------------------------------
function showTopicsAndResources(topicsData) {
    appendMessage('assistant', escapeHtml(topicsData.reply));

    studyContext.availableTopics = topicsData.topics || [];

    let topicsHtml = '';
    studyContext.availableTopics.forEach((t, i) => {
        topicsHtml += `
            <div class="selection-item">
                <div class="selection-left">
                    <input type="checkbox" id="topic-${i}" class="selection-checkbox" ${t.included ? 'checked' : ''}>
                    <label for="topic-${i}"><strong>${escapeHtml(t.course)}:</strong> ${escapeHtml(t.topic)}</label>
                </div>
            </div>
        `;
    });

    const uniqueCourses = [...new Set(studyContext.availableTopics.map(t => t.course))];
    let courseUploadsHtml = '';
    uniqueCourses.forEach((course, i) => {
        courseUploadsHtml += `
            <div style="margin-bottom: 16px; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; background: #f8fafc;">
                <h5 style="margin-bottom: 8px; color: var(--indigo-dark);">${escapeHtml(course)}</h5>
                <label class="material-upload-label" style="cursor:pointer; display: block; margin-bottom: 8px;">
                    <span style="font-size:1.2rem;">📁</span> Upload Syllabus/Slides
                    <input type="file" class="hidden" accept=".pdf,.ppt,.pptx">
                </label>
                <div style="display:flex; align-items:center; gap:6px;">
                    <input type="checkbox" id="req-video-${i}" checked style="width:14px;height:14px;">
                    <label for="req-video-${i}" style="font-size: 0.85rem; color: var(--text-main);">Request video explanations (NPTEL / YouTube)</label>
                </div>
            </div>
        `;
    });

    const cardId = 'topics-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4>Syllabus Scope & Lecture Materials</h4>
            <p class="mb-2" style="font-size:0.9rem;font-weight:600;">Core Topics:</p>
            <div class="selection-list">
                ${topicsHtml}
            </div>
            
            <p class="mb-2" style="font-size:0.9rem;font-weight:600; margin-top: 20px;">Provide Course Materials:</p>
            ${courseUploadsHtml}

            <button class="btn btn-primary w-full mt-4" onclick="submitMaterials('${cardId}')">Curate Learning Materials</button>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}

window.submitMaterials = async function(cardId) {
    const card = document.getElementById(cardId);
    if(card) {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if(btn) btn.textContent = "Curating... ✓";
    }
    
    appendMessage('user', "I have specified my syllabus scope and requested material curation.");
    
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Curating authoritative video lectures from NPTEL & YouTube... ⏳</span>`);
    
    try {
        const selectedTopics = (studyContext.availableTopics || []).filter((t, idx) => {
            const cb = document.getElementById(`topic-${idx}`);
            return cb ? cb.checked : true;
        });

        const materialsData = await apiClient.curateMaterials({
            courses: studyContext.courses.filter(c => c.selected !== false),
            topics: selectedTopics
        });

        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        
        showCuratedMaterials(materialsData);
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        appendMessage('assistant', `⚠️ Could not curate materials: ${err.message}`);
    }
}

// ----------------------------------------------------
// UI Flow: Step 3 - Curated Materials & Constraints
// ----------------------------------------------------
function showCuratedMaterials(materials) {
    appendMessage('assistant', escapeHtml(materials.reply));

    let videosHtml = '';
    (materials.videos || []).forEach(v => {
        const badgeClass = v.platform === 'YouTube' ? 'badge-youtube' : 'badge-nptel';
        const icon = v.platform === 'YouTube' ? '▶️' : '🎓';
        videosHtml += `
            <div class="video-item">
                <div class="video-icon">${icon}</div>
                <div>
                    <a href="${escapeHtml(v.url)}" target="_blank" class="video-title">${escapeHtml(v.title)}</a>
                    <span class="video-meta"><span class="${badgeClass}">${escapeHtml(v.platform)}</span> ${escapeHtml(v.channel || 'Curated Resource')}</span>
                </div>
            </div>
        `;
    });

    const cardId = 'materials-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4>Curated Video Explanations</h4>
            <div style="margin-bottom:20px;">
                ${videosHtml}
            </div>
            
            <h4 style="margin-top:24px;">Personal Study Constraints</h4>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;">
                Add personal rules for Gemma 4 (e.g. "prefer studying in morning", "keep 2 hours for sports in evening").
            </p>
            <div class="chat-input-wrapper" style="margin-bottom: 16px;">
                <textarea id="constraints-input-${cardId}" rows="2" placeholder="e.g. Keep evening slots for revision..."></textarea>
            </div>

            <button class="btn btn-primary w-full" onclick="generateRoadmap('${cardId}')">Build My Final Roadmap with Gemma 4</button>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}

window.generateRoadmap = async function(cardId) {
    const card = document.getElementById(cardId);
    let constraints = "";
    if(card) {
        const inputArea = document.getElementById(`constraints-input-${cardId}`);
        if(inputArea) {
            constraints = inputArea.value.trim();
        }
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if(btn) btn.textContent = "Building... ✓";
    }
    
    let msg = "Generate my personalized roadmap.";
    if (constraints) {
        msg += `\nMy constraints: "${constraints}"`;
    }
    appendMessage('user', msg);
    
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Gemma 4 is synthesizing credit weights, buffer days, and pedagogical constraints... ⏳</span>`);
    
    try {
        const roadmapData = await apiClient.generateRoadmap({
            courses: studyContext.courses.filter(c => c.selected !== false),
            constraints: constraints,
            daily_hours: studyContext.study_hours || 4,
            start_date: studyContext.start_date
        });

        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        
        showRoadmap(roadmapData);
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        appendMessage('assistant', `⚠️ Could not generate roadmap: ${err.message}`);
    }
}

// ----------------------------------------------------
// UI Flow: Step 4 - Final Roadmap
// ----------------------------------------------------
function showRoadmap(planner) {
    appendMessage('assistant', escapeHtml(planner.reply));

    const studyPlan = planner.study_plan || [];

    // TIMELINE VIEW
    let timelineHtml = '<div class="timeline">';
    studyPlan.forEach(day => {
        let details = '';
        (day.blocks || []).forEach(b => {
            let topicsStr = b.topics ? b.topics.join(", ") : (b.note || "");
            const timeStr = b.time_range ? `[${b.time_range}] ` : '';
            details += `<strong>${escapeHtml(b.course || b.type.toUpperCase())}</strong>: ${escapeHtml(topicsStr)} <span style="color:var(--text-muted); font-size:0.8rem;">${timeStr}(${b.hours}h)</span><br>`;
        });
        timelineHtml += `
            <div class="timeline-node">
                <div class="timeline-date">${escapeHtml(day.date)}</div>
                <div class="timeline-title">${day.total_hours} Hours Scheduled</div>
                <div class="timeline-desc">${details}</div>
            </div>
        `;
    });
    timelineHtml += '</div>';

    // SCHEDULE VIEW
    let scheduleHtml = '';
    studyPlan.forEach(day => {
        let blocksHtml = '';
        (day.blocks || []).forEach(b => {
            let badgeHtml = '';
            if (b.type === 'study') badgeHtml = `<span class="badge-study">Study</span>`;
            else if (b.type === 'revision') badgeHtml = `<span class="badge-revision">Revision</span>`;
            else badgeHtml = `<span class="badge-buffer">Buffer</span>`;

            let pillsHtml = '';
            if (b.topics) {
                b.topics.forEach(t => {
                    pillsHtml += `<span class="topic-pill">${escapeHtml(t)}</span>`;
                });
            } else if (b.note) {
                pillsHtml += `<span class="topic-pill">${escapeHtml(b.note)}</span>`;
            }

            let refHtml = '';
            if (b.reference) {
                refHtml = `<div class="block-reference">🔗 ${escapeHtml(b.reference)}</div>`;
            }
            
            const timeDisplay = b.time_range ? b.time_range : `${b.hours}h`;

            blocksHtml += `
                <div class="schedule-block">
                    <div class="block-time" style="font-size:0.95rem;">${escapeHtml(timeDisplay)}</div>
                    <div class="block-content">
                        <div class="block-header">
                            <span class="block-course">${escapeHtml(b.course || 'Study Block')}</span>
                            ${badgeHtml}
                        </div>
                        <div class="topic-pills">
                            ${pillsHtml}
                        </div>
                        ${refHtml}
                    </div>
                </div>
            `;
        });
        scheduleHtml += `
            <div class="schedule-day">
                <div class="schedule-header">
                    <span>${escapeHtml(day.date)}</span>
                    <span>Total: ${day.total_hours}h</span>
                </div>
                ${blocksHtml}
            </div>
        `;
    });

    const cardId = 'roadmap-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:12px; margin-bottom:16px;">
                <h4 style="border-bottom:none; margin:0; padding:0;">Personalized Study Roadmap</h4>
                <div class="roadmap-controls" style="margin-bottom:0;">
                    <button class="btn btn-outline btn-sm" onclick="switchRoadmapView('${cardId}', 'timeline')">Timeline</button>
                    <button class="btn btn-outline btn-sm" onclick="switchRoadmapView('${cardId}', 'schedule')">Daily blocks</button>
                </div>
            </div>
            <div id="${cardId}-timeline-view" class="roadmap-content hidden">
                ${timelineHtml}
            </div>
            <div id="${cardId}-schedule-view" class="roadmap-content">
                ${scheduleHtml}
            </div>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}

window.switchRoadmapView = function(cardId, viewType) {
    const timelineView = document.getElementById(`${cardId}-timeline-view`);
    const scheduleView = document.getElementById(`${cardId}-schedule-view`);
    
    if (viewType === 'timeline') {
        timelineView.classList.remove('hidden');
        scheduleView.classList.add('hidden');
    } else {
        timelineView.classList.add('hidden');
        scheduleView.classList.remove('hidden');
    }
};
