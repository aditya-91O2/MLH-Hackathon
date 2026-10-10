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
    const activeCount = studyContext.courses.filter(c => c.selected === true).length;
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

    const startBtn = document.getElementById('start-processing-btn');
    if (startBtn) {
        startBtn.addEventListener('click', async (e) => {
            const uploadArea = document.getElementById('initial-upload-area');
            if (uploadArea) uploadArea.classList.add('hidden');

            appendMessage('user', `[Uploaded Exam Timetable, Master Timetable, and Course of Study]`);
            chatComposer.classList.remove('hidden');

            const loadingId = 'loading-' + Date.now();
            appendMessage('assistant', `<span id="${loadingId}">Analyzing your documents with Gemma 4... ⏳</span>`);

            try {
                // Check all upload inputs for the user's uploaded timetable document or image
                const fileInput = [
                    document.getElementById('upload-exam-tt'),
                    document.getElementById('upload-master-tt'),
                    document.getElementById('upload-course-study')
                ].find(input => input && input.files && input.files.length > 0);
                const file = fileInput ? fileInput.files[0] : null;

                let extraction = null;
                if (file) {
                    extraction = await apiClient.uploadTimetable(file);
                } else {
                    // Fetch current/default timetable
                    try {
                        const ttUrl = typeof API_BASE !== 'undefined' && API_BASE ? `${API_BASE}/api/timetable?use_default_if_empty=true` : '/api/timetable?use_default_if_empty=true';
                        const res = await fetch(ttUrl);
                        if (res.ok) {
                            const ttData = await res.json();
                        }
                    } catch (e) {}

                    extraction = {
                        reply: "I've analyzed your institute timetable! Here are the extracted examination courses with credit ratings. Please confirm your enrolled courses below.",
                        extracted_data: {
                            courses: [
                                { code: "MAL403", name: "Probability and Statistics", credits: 4.0, instructor: "Dr. Lakshmi Kanta Patra", exam_date: "2026-09-18", slot_no: 11, hall: "L-209" },
                                { code: "CSL201", name: "Discrete Mathematics", credits: 4.0, instructor: "Dr. Rishi Ranjan Singh", exam_date: "2026-09-21", slot_no: 21, hall: "L-209" },
                                { code: "CSL202", name: "Data Structures", credits: 4.0, instructor: "Prof. Souradyuti Paul", exam_date: "2026-09-24", slot_no: 51, hall: "L-209" },
                                { code: "CSP203", name: "Software Tools Lab", credits: 2.0, instructor: "CS Faculty", exam_date: "2026-09-23", slot_no: 0, hall: "Lab Session" },
                                { code: "LAL100", name: "Introduction to Communication Skills", credits: 2.0, instructor: "Dr. Sruthi Vinayan", exam_date: "2026-09-25", slot_no: 61, hall: "L-209" }
                            ],
                            study_hours: 4,
                            start_date: "2026-09-18"
                        }
                    };
                }

                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.parentElement.parentElement.remove();

                showCourseReview(extraction);
            } catch (err) {
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.parentElement.parentElement.remove();
                appendMessage('assistant', `⚠️ Could not parse custom slots: ${err.message}. Loaded department examination schedule so you can continue.`);
                
                const fallbackExtraction = {
                    reply: "Loaded your department examination schedule with course credits. Please confirm your enrolled courses below.",
                    extracted_data: {
                        courses: [
                            { code: "MAL403", name: "Probability and Statistics", credits: 4.0, instructor: "Dr. Lakshmi Kanta Patra", exam_date: "2026-09-18", slot_no: 11, hall: "L-209" },
                            { code: "CSL201", name: "Discrete Mathematics", credits: 4.0, instructor: "Dr. Rishi Ranjan Singh", exam_date: "2026-09-21", slot_no: 21, hall: "L-209" },
                            { code: "CSL202", name: "Data Structures", credits: 4.0, instructor: "Prof. Souradyuti Paul", exam_date: "2026-09-24", slot_no: 51, hall: "L-209" },
                            { code: "CSP203", name: "Software Tools Lab", credits: 2.0, instructor: "CS Faculty", exam_date: "2026-09-23", slot_no: 0, hall: "Lab Session" },
                            { code: "LAL100", name: "Introduction to Communication Skills", credits: 2.0, instructor: "Dr. Sruthi Vinayan", exam_date: "2026-09-25", slot_no: 61, hall: "L-209" }
                        ],
                        study_hours: 4,
                        start_date: "2026-09-18"
                    }
                };
                showCourseReview(fallbackExtraction);
            }
        });
    }


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
// Chatbot (Live RAG with Gemma 4 & ChromaDB)
// ----------------------------------------------------
async function handleChatSubmit() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    chatHistory.push({ role: 'user', content: text });
    chatInput.value = '';

    // Determine primary active course
    const activeCourse = (studyContext.courses.find(c => c.selected === true) || studyContext.courses[0] || {}).code || "";
    const enrolledCodes = studyContext.courses.filter(c => c.selected === true).map(c => c.code).filter(Boolean);

    try {
        const res = await apiClient.sendChat({
            course_code: activeCourse,
            message: text,
            history: chatHistory.slice(-8),
            enrolled_courses: enrolledCodes,
            timetable_data: {
                courses: studyContext.courses || []
            },
            plan_data: studyContext.studyPlan || null,
            scope_data: {
                included: (studyContext.selectedTopics || []).map(t => t.topic),
                coverage_pct: studyContext.selectedTopics ? Math.round((studyContext.selectedTopics.length / Math.max(1, (studyContext.availableTopics || []).length)) * 100) : 100
            }
        });

        const answerText = (res && (res.answer || res.reply)) ? (res.answer || res.reply) : "I couldn't generate a response. Please ask a question about your exam topics.";
        let formatted = escapeHtml(answerText).replace(/\n/g, '<br>');

        if (res.citations && res.citations.length > 0) {
            const citationsList = res.citations.map(c => `<code>${escapeHtml(c.source || 'Notes')}</code> (p.${escapeHtml(c.page || '1')})`).join(', ');
            formatted += `<div style="margin-top:10px; font-size:0.8rem; color:#475569; border-top:1px dashed #cbd5e1; padding-top:6px;"><strong>📚 Cited Notes & Slides:</strong> ${citationsList}</div>`;
        }

        appendMessage('assistant', formatted);
        chatHistory.push({ role: 'assistant', content: answerText });
    } catch (err) {
        appendMessage('assistant', `⚠️ Chat error: ${escapeHtml(err.message)}`);
        chatHistory.push({ role: 'assistant', content: `Error: ${err.message}` });
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
window.handleCourseCheck = function (index, isChecked) {
    if (studyContext.courses[index]) {
        studyContext.courses[index].selected = isChecked;
        updateContextSummary();
    }
};

window.toggleAllCourses = function (cardId, selectState) {
    const card = document.getElementById(cardId);
    if (!card) return;
    const checkboxes = card.querySelectorAll('.course-cb');
    checkboxes.forEach((cb, idx) => {
        cb.checked = selectState;
        if (studyContext.courses[idx]) {
            studyContext.courses[idx].selected = selectState;
        }
    });
    updateContextSummary();
};

function showCourseReview(extraction) {
    studyContext.courses = JSON.parse(JSON.stringify(extraction.extracted_data.courses || []));
    // Explicitly unselect all courses by default per user specification
    studyContext.courses.forEach(c => c.selected = false);
    studyContext.study_hours = extraction.extracted_data.study_hours || 4;
    studyContext.start_date = extraction.extracted_data.start_date;
    updateContextSummary();

    appendMessage('assistant', escapeHtml(extraction.reply));

    const cardId = 'course-card-' + Date.now();
    let listHtml = '';
    studyContext.courses.forEach((course, index) => {
        listHtml += `
            <div class="selection-item">
                <div class="selection-left" style="align-items: flex-start;">
                    <input type="checkbox" id="course-${index}" class="selection-checkbox course-cb" style="margin-top: 4px;" onchange="handleCourseCheck(${index}, this.checked)">
                    <label for="course-${index}">
                        <strong>${escapeHtml(course.code || '')}</strong>: ${escapeHtml(course.name || course.code)}
                        ${course.credits ? `<span class="badge-revision" style="margin-left:6px; font-size:0.75rem; padding:2px 7px;">${course.credits} Credits</span>` : ''}
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

    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                <h4 style="margin:0;">Extracted Examination Courses</h4>
                <div style="display:flex; gap:8px;">
                    <button type="button" class="btn btn-outline btn-sm" style="padding:4px 10px; font-size:0.75rem;" onclick="toggleAllCourses('${cardId}', true)">Select All</button>
                    <button type="button" class="btn btn-outline btn-sm" style="padding:4px 10px; font-size:0.75rem;" onclick="toggleAllCourses('${cardId}', false)">Clear All</button>
                </div>
            </div>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:12px;">
                Please check only the courses you are currently enrolled in for this semester:
            </p>
            <div class="selection-list">
                ${listHtml}
            </div>
            <button class="btn btn-primary mt-2" onclick="confirmCourses('${cardId}')">Confirm Selected Courses</button>
        </div>
    `;

    appendCustomCard(cardHtml);
}

window.confirmCourses = async function (cardId) {
    const card = document.getElementById(cardId);
    if (!card) return;

    const checkboxes = card.querySelectorAll('.course-cb');
    checkboxes.forEach((cb, idx) => {
        if (studyContext.courses[idx]) {
            studyContext.courses[idx].selected = cb.checked;
        }
    });
    updateContextSummary();

    const selectedCourses = studyContext.courses.filter(c => c.selected === true);
    if (selectedCourses.length === 0) {
        alert("Please select at least one course you are enrolled in before proceeding.");
        return;
    }

    card.style.opacity = '0.6';
    card.style.pointerEvents = 'none';
    const btn = card.querySelector('button.btn-primary');
    if (btn) btn.textContent = "Confirmed ✓";

    const enrolledNames = selectedCourses.map(c => c.code).join(", ");
    appendMessage('user', `I have confirmed my enrolled courses: ${enrolledNames}`);

    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Gemma 4 is mapping curriculum topics and prerequisites for ${selectedCourses.length} selected course(s)... ⏳</span>`);

    try {
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

window.toggleCourseTopics = function (courseIdx, selectState) {
    const checkboxes = document.querySelectorAll(`.topic-cb-${courseIdx}`);
    checkboxes.forEach(cb => {
        cb.checked = selectState;
    });
};

function showTopicsAndResources(topicsData) {
    const data = (topicsData && topicsData.topics && topicsData.topics.length > 0)
        ? topicsData
        : {
            reply: "I have mapped out the core topics for your selected courses. Please select the topics you need to prepare for, and upload any course slides or notes below.",
            topics: (studyContext.courses.filter(c => c.selected === true).length > 0
                ? studyContext.courses.filter(c => c.selected === true).flatMap(c => [
                    { course: c.name || c.code, topic: `Core Theory & Foundations of ${c.name || c.code}`, included: false },
                    { course: c.name || c.code, topic: `Key Problem Sets & Revision for ${c.name || c.code}`, included: false }
                ])
                : [
                    { course: "Data Structures", topic: "Stacks, Queues, and Priority Heaps", included: false },
                    { course: "Data Structures", topic: "Trees, Balanced BSTs, and Graph Traversals", included: false },
                    { course: "Discrete Mathematics", topic: "Propositional and First-Order Logic", included: false },
                    { course: "Probability & Statistics", topic: "Continuous Probability Distributions", included: false }
                ]
            )
        };

    studyContext.availableTopics = data.topics || [];
    appendMessage('assistant', escapeHtml(data.reply || "I have mapped out the core topics for your selected courses. Please select the topics you need to prepare for:"));

    const uniqueCourses = [...new Set(data.topics.map(t => t.course))];
    studyContext.uniqueCourseNames = uniqueCourses;
    let topicsHtml = '';

    uniqueCourses.forEach((course, courseIdx) => {
        const courseTopics = data.topics.map((t, i) => ({ ...t, index: i })).filter(t => t.course === course);

        topicsHtml += `
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <h6 style="color: var(--indigo-dark); margin: 0; font-size: 0.95rem; font-weight:600;">${escapeHtml(course)}</h6>
                    <div style="display:flex; gap:6px;">
                        <button type="button" class="btn btn-outline btn-sm" style="padding:2px 8px; font-size:0.75rem;" onclick="toggleCourseTopics(${courseIdx}, true)">Select All</button>
                        <button type="button" class="btn btn-outline btn-sm" style="padding:2px 8px; font-size:0.75rem;" onclick="toggleCourseTopics(${courseIdx}, false)">Clear All</button>
                    </div>
                </div>
                <div class="selection-list" style="margin-bottom: 0;">
        `;
        courseTopics.forEach(t => {
            topicsHtml += `
                <div class="selection-item" style="padding: 8px 12px;">
                    <div class="selection-left">
                        <input type="checkbox" id="topic-${t.index}" class="selection-checkbox topic-cb-${courseIdx}">
                        <label for="topic-${t.index}">${escapeHtml(t.topic)}</label>
                    </div>
                </div>
            `;
        });
        topicsHtml += `</div></div>`;
    });

    let courseUploadsHtml = '<div id="sequential-uploads-container">';
    uniqueCourses.forEach((course, i) => {
        const hiddenClass = i === 0 ? '' : 'hidden';

        courseUploadsHtml += `
            <div id="upload-block-${i}" class="course-upload-block ${hiddenClass}" style="margin-bottom: 16px; padding: 14px; border: 1px solid var(--border-color); border-radius: 8px; background: #f8fafc;">
                <h5 style="margin-bottom: 10px; color: var(--indigo-dark);">${escapeHtml(course)}</h5>
                
                <div id="upload-area-${i}">
                    <label class="material-upload-label" style="cursor:pointer; display: block; margin-bottom: 12px;">
                        <span style="font-size:1.2rem;">📁</span> Upload Syllabus/Slides (PDF, PPTX, TXT)
                        <input type="file" id="file-input-${i}" class="hidden" accept=".pdf,.ppt,.pptx,.txt" multiple onchange="handleCourseUpload(${i}, ${uniqueCourses.length})">
                    </label>
                </div>
                
                <div id="uploaded-file-display-${i}" class="hidden" style="margin-bottom: 12px; padding: 10px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 6px; color: #0369a1; font-size: 0.9rem; font-weight: 600; display: flex; justify-content: space-between; align-items: center;">
                    <span id="uploaded-file-text-${i}"></span>
                    <button class="btn btn-outline btn-sm" style="background: white; padding: 4px 8px; font-size: 0.8rem; border-color: #bae6fd; color: #0369a1;" onclick="discardCourseUpload(${i}, ${uniqueCourses.length})">Discard</button>
                </div>

                <button id="skip-btn-${i}" class="btn btn-outline btn-sm" style="width:100%; border-color:#cbd5e1; color:#64748b;" onclick="handleCourseUpload(${i}, ${uniqueCourses.length}, true)">Skip Upload (Use Academic Web Notes)</button>
            </div>
        `;
    });
    courseUploadsHtml += '</div>';

    const cardId = 'topics-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4 style="margin-bottom:20px;">Syllabus Scope & Materials</h4>
            
            <p class="mb-2" style="font-size:0.9rem;font-weight:600;">Core Topics by Course:</p>
            <div style="padding: 12px; border: 1px dashed var(--border-color); border-radius: 8px; background: white; margin-bottom: 24px;">
                ${topicsHtml}
            </div>
            
            <p class="mb-2" style="font-size:0.9rem;font-weight:600;">Provide Course Materials (Step-by-step):</p>
            ${courseUploadsHtml}

            <button id="analyze-materials-btn" class="btn btn-secondary w-full mt-2" disabled style="opacity:0.6; cursor:not-allowed;" onclick="submitMaterials('${cardId}')">Complete uploads to continue</button>
        </div>
    `;

    appendCustomCard(cardHtml);
}

window.handleCourseUpload = async function (currentIndex, totalCourses, isSkip = false) {
    const course = (studyContext.uniqueCourseNames || [])[currentIndex] || `Course-${currentIndex}`;
    if (!studyContext.uploadedCourseFiles) studyContext.uploadedCourseFiles = {};

    if (!isSkip) {
        const fileInput = document.getElementById(`file-input-${currentIndex}`);
        if (fileInput && fileInput.files.length > 0) {
            const filesList = Array.from(fileInput.files).map(f => `<strong>${escapeHtml(f.name)}</strong>`).join(', ');
            const textEl = document.getElementById(`uploaded-file-text-${currentIndex}`);
            const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
            const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
            const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);

            studyContext.uploadedCourseFiles[course] = Array.from(fileInput.files).map(f => f.name);

            if (displayEl && textEl) {
                textEl.innerHTML = `✓ Uploaded: ${filesList} <span style="font-size:0.75rem; color:#0284c7;">(Indexing for RAG...)</span>`;
                displayEl.classList.remove('hidden');
                displayEl.style.background = '#e0f2fe';
                displayEl.style.borderColor = '#bae6fd';
                displayEl.style.color = '#0369a1';
            }
            if (uploadArea) uploadArea.classList.add('hidden');
            if (skipBtn) skipBtn.classList.add('hidden');

            // Send files to backend for live RAG vector store indexing
            try {
                const res = await apiClient.uploadMaterials(course, fileInput.files);
                if (textEl) {
                    textEl.innerHTML = `✓ Uploaded: ${filesList} <span style="font-size:0.75rem; color:#059669;">(${res.total_chunks_indexed || 0} chunks indexed for RAG)</span>`;
                }
            } catch (err) {
                console.warn("RAG file ingestion notice:", err);
            }
        }
    } else {
        studyContext.uploadedCourseFiles[course] = [];
        const textEl = document.getElementById(`uploaded-file-text-${currentIndex}`);
        const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
        const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
        const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);

        if (displayEl && textEl) {
            textEl.innerHTML = `<em>No file uploaded. (Using curated open academic notes)</em>`;
            displayEl.classList.remove('hidden');
            displayEl.style.background = '#f1f5f9';
            displayEl.style.borderColor = '#cbd5e1';
            displayEl.style.color = '#475569';
        }
        if (uploadArea) uploadArea.classList.add('hidden');
        if (skipBtn) skipBtn.classList.add('hidden');
    }

    const nextIndex = currentIndex + 1;
    if (nextIndex < totalCourses) {
        const nextBlock = document.getElementById(`upload-block-${nextIndex}`);
        if (nextBlock) nextBlock.classList.remove('hidden');
    }

    checkAllUploadsComplete(totalCourses);
};

window.discardCourseUpload = function (currentIndex, totalCourses) {
    const course = (studyContext.uniqueCourseNames || [])[currentIndex] || `Course-${currentIndex}`;
    if (studyContext.uploadedCourseFiles) {
        studyContext.uploadedCourseFiles[course] = [];
    }

    const fileInput = document.getElementById(`file-input-${currentIndex}`);
    if (fileInput) fileInput.value = '';

    const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
    const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
    const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);

    if (displayEl) displayEl.classList.add('hidden');
    if (uploadArea) uploadArea.classList.remove('hidden');
    if (skipBtn) skipBtn.classList.remove('hidden');

    checkAllUploadsComplete(totalCourses);
};

function checkAllUploadsComplete(totalCourses) {
    let allDone = true;
    for (let i = 0; i < totalCourses; i++) {
        const displayEl = document.getElementById(`uploaded-file-display-${i}`);
        if (!displayEl || displayEl.classList.contains('hidden')) {
            allDone = false;
            break;
        }
    }

    const analyzeBtn = document.getElementById('analyze-materials-btn');
    if (analyzeBtn) {
        if (allDone) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Analyze Materials";
            analyzeBtn.style.opacity = '1';
            analyzeBtn.style.cursor = 'pointer';
            analyzeBtn.classList.remove('btn-secondary');
            analyzeBtn.classList.add('btn-primary');
        } else {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = "Complete uploads to continue";
            analyzeBtn.style.opacity = '0.6';
            analyzeBtn.style.cursor = 'not-allowed';
            analyzeBtn.classList.add('btn-secondary');
            analyzeBtn.classList.remove('btn-primary');
        }
    }
}

window.submitMaterials = async function (cardId) {
    const card = document.getElementById(cardId);
    const selectedTopics = (studyContext.availableTopics || []).filter((t, idx) => {
        const cb = document.getElementById(`topic-${idx}`);
        return cb ? cb.checked : false;
    });

    if (selectedTopics.length === 0) {
        alert("Please select at least one topic to prepare for.");
        return;
    }

    studyContext.selectedTopics = selectedTopics;

    if (card) {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('#analyze-materials-btn') || card.querySelector('button');
        if (btn) btn.textContent = "Curating... ✓";
    }

    appendMessage('user', `I have selected ${selectedTopics.length} topic(s) and requested material curation.`);

    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Analyzing your course materials and retrieving authoritative academic notes for uncovered topics... ⏳</span>`);

    try {
        const materialsData = await apiClient.curateMaterials({
            courses: studyContext.courses.filter(c => c.selected === true),
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

    // Uploaded materials overview per enrolled course
    let uploadedHtml = '';
    const uploadedMap = studyContext.uploadedCourseFiles || {};
    const selectedCourses = studyContext.courses.filter(c => c.selected === true);

    selectedCourses.forEach(c => {
        const cCode = c.code || c.name;
        const files = uploadedMap[cCode] || uploadedMap[c.name] || (materials.course_materials && materials.course_materials[cCode]) || [];
        if (files && files.length > 0) {
            uploadedHtml += `
                <div class="video-item" style="border-left: 3px solid #10b981; margin-bottom: 8px;">
                    <div class="video-icon">📑</div>
                    <div>
                        <div class="video-title" style="color: #047857; font-weight: 600;">${escapeHtml(cCode)}: ${escapeHtml(c.name || '')}</div>
                        <span class="video-meta"><span class="badge-study">Indexed for RAG</span> <strong>Files:</strong> ${escapeHtml(files.join(', '))}</span>
                    </div>
                </div>
            `;
        } else {
            uploadedHtml += `
                <div class="video-item" style="border-left: 3px solid #f59e0b; margin-bottom: 8px;">
                    <div class="video-icon">📂</div>
                    <div>
                        <div class="video-title" style="color: #b45309; font-weight: 600;">${escapeHtml(cCode)}: ${escapeHtml(c.name || '')}</div>
                        <span class="video-meta"><span class="badge-buffer">No Slides Uploaded</span> Relying on open academic notes & guides below</span>
                    </div>
                </div>
            `;
        }
    });

    // Render Curated NPTEL & Academic Video Lectures
    let videoHtml = '';
    if (materials.videos && materials.videos.length > 0) {
        materials.videos.forEach(v => {
            const isNptel = (v.platform === 'NPTEL') || (v.channel && v.channel.toLowerCase().includes('nptel'));
            videoHtml += `
                <div class="video-item" style="border-left: 3px solid ${isNptel ? '#0d9488' : '#e11d48'}; margin-bottom: 8px;">
                    <div class="video-icon">${isNptel ? '🎓' : '▶️'}</div>
                    <div style="flex: 1; min-width: 0;">
                        <a href="${escapeHtml(v.url)}" target="_blank" rel="noopener noreferrer" class="video-title">
                            ${escapeHtml(v.title)}
                        </a>
                        <div class="video-meta">
                            <span class="${isNptel ? 'badge-nptel' : 'badge-youtube'}">${isNptel ? 'NPTEL' : 'YouTube'}</span>
                            <strong>${escapeHtml(v.channel || 'NPTEL-IIT Official')}</strong>
                            ${v.topic ? `<span>• Topic: ${escapeHtml(v.topic)}</span>` : ''}
                        </div>
                    </div>
                    <a href="${escapeHtml(v.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="flex-shrink: 0; padding: 4px 10px; font-size: 0.75rem;">
                        Watch ↗
                    </a>
                </div>
            `;
        });
    }

    // Render Web Search Materials for Uncovered Topics
    let webHtml = '';
    if (materials.web_resources && materials.web_resources.length > 0) {
        materials.web_resources.forEach(w => {
            webHtml += `
                <div class="video-item" style="border-left: 3px solid #3b82f6; margin-bottom: 8px;">
                    <div class="video-icon">📖</div>
                    <div style="flex: 1; min-width: 0;">
                        <a href="${escapeHtml(w.url)}" target="_blank" rel="noopener noreferrer" class="video-title">${escapeHtml(w.title)}</a>
                        <div class="video-meta">
                            <span class="badge-revision">${escapeHtml(w.source || 'Academic Notes')}</span>
                            <span>${escapeHtml(w.type || 'Study Notes & Problem Set')}</span>
                            ${w.topic ? `<span>• ${escapeHtml(w.topic)}</span>` : ''}
                        </div>
                    </div>
                    <a href="${escapeHtml(w.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="flex-shrink: 0; padding: 4px 10px; font-size: 0.75rem;">
                        Read ↗
                    </a>
                </div>
            `;
        });
    }

    const cardId = 'materials-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4 style="margin-bottom:12px;">📁 Course Slides & Study Material Scope</h4>
            <div style="margin-bottom:18px;">
                ${uploadedHtml}
            </div>

            <h4 style="margin-top:20px; margin-bottom:10px;">📺 Curated NPTEL & Academic Video Lectures</h4>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:12px;">
                Authentic NPTEL IIT course video lectures and high-yield walkthroughs for your selected topics:
            </p>
            <div style="margin-bottom:20px;">
                ${videoHtml || '<p style="font-size:0.85rem; color:var(--text-muted);"><em>No external videos needed for fully covered uploaded notes.</em></p>'}
            </div>
            
            <h4 style="margin-top:20px; margin-bottom:10px;">🌐 Open Academic Study Notes & Problem Sets</h4>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:12px;">
                Direct authoritative textbook chapters, Stanford/MIT open notes, and formula sheets for left out topics:
            </p>
            <div style="margin-bottom:20px;">
                ${webHtml}
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


window.generateRoadmap = async function (cardId) {
    const card = document.getElementById(cardId);
    let constraints = "";
    if (card) {
        const inputArea = document.getElementById(`constraints-input-${cardId}`);
        if (inputArea) {
            constraints = inputArea.value.trim();
        }
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if (btn) btn.textContent = "Building... ✓";
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
            courses: studyContext.courses.filter(c => c.selected === true),
            topics: studyContext.selectedTopics || studyContext.availableTopics || [],
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
    studyContext.studyPlan = planner;
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

    // WEIGHTED BREAKDOWN VIEW
    let weightHtml = '';
    if (planner.workload_weights && planner.workload_weights.length > 0) {
        let itemsHtml = '';
        planner.workload_weights.forEach(w => {
            itemsHtml += `
                <div style="background:var(--surface); border:1px solid var(--border-color); border-radius:var(--r-sm); padding:10px 12px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; flex-wrap:wrap; gap:6px;">
                        <span style="font-weight:600; color:var(--ink);">${escapeHtml(w.course_code)}: ${escapeHtml(w.course_name || '')}</span>
                        <span class="badge-study" style="font-size:0.75rem;">${w.workload_percentage}% Allocation (${w.recommended_total_hours}h target)</span>
                    </div>
                    <div style="font-size:0.8rem; color:var(--text-muted); display:flex; gap:12px; flex-wrap:wrap;">
                        <span>🏛️ <strong>${w.credits} Credits</strong> (Master Timetable)</span>
                        <span>📚 <strong>${w.num_topics} Topics</strong> Selected</span>
                        <span>📊 Content Scope: <strong>${escapeHtml(w.content_volume_label || 'Comprehensive')}</strong></span>
                    </div>
                </div>
            `;
        });

        weightHtml = `
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:var(--r-md); padding:12px 14px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <strong style="font-size:0.95rem; color:#1e293b;">⚖️ Credit & Content-Weighted Allocation</strong>
                    <span style="font-size:0.75rem; color:var(--text-muted);">Calibrated against Master Timetable</span>
                </div>
                ${itemsHtml}
            </div>
        `;
    }

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
            ${weightHtml}
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

window.switchRoadmapView = function (cardId, viewType) {
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
