document.addEventListener('DOMContentLoaded', () => {
    console.log("Study Planner - Strict Format Demo");
    loadDemoData();
    initUI();
});

// State
let demoData = null;
let studyContext = { courses: [] };

// DOM Elements
const chatHistoryEl = document.getElementById('chat-history');
const initialUpload = document.getElementById('initial-upload');
const chatComposer = document.getElementById('chat-composer');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');

async function loadDemoData() {
    try {
        const res = await fetch('data/demo-data.json');
        demoData = await res.json();
    } catch (e) {
        console.error("Failed to load demo data:", e);
    }
}

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
    if (demoData && demoData.gemma_extraction) {
        document.getElementById('summary-study-hours').textContent = demoData.gemma_extraction.extracted_data.study_hours;
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
        startBtn.addEventListener('click', (e) => {
            const uploadArea = document.getElementById('initial-upload-area');
            if (uploadArea) uploadArea.classList.add('hidden');
            
            appendMessage('user', `[Uploaded Exam Timetable, Master Timetable, and Course of Study]`);
            chatComposer.classList.remove('hidden');
            
            // Show processing message
            const loadingId = 'loading-' + Date.now();
            appendMessage('assistant', `<span id="${loadingId}">Analyzing your documents with Gemma... ⏳</span>`);
            
            // Wait 1.5 seconds to simulate Gemma processing
            setTimeout(() => {
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.parentElement.parentElement.remove();
                
                showCourseReview();
            }, 1500);
        });
    }

    chatSend.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSubmit();
        }
    });
}

function handleChatSubmit() {
    const text = chatInput.value.trim();
    if (!text) return;
    appendMessage('user', text);
    chatInput.value = '';
    
    setTimeout(() => {
        appendMessage('assistant', "[Demo Mode] I am currently disconnected from live processing. Please follow the demonstrated roadmap workflow cards above.");
    }, 600);
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = `<p>${text}</p>`; // Not escaping here so we can inject spans for loading
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
// UI Flow: Step 1 - Course Review
// ----------------------------------------------------
function showCourseReview() {
    const extraction = demoData.gemma_extraction;
    
    // Deep copy into local state
    studyContext.courses = JSON.parse(JSON.stringify(extraction.extracted_data.courses));
    updateContextSummary();

    appendMessage('assistant', escapeHtml(extraction.reply));
    
    let listHtml = '';
    studyContext.courses.forEach((course, index) => {
        listHtml += `
            <div class="selection-item">
                <div class="selection-left" style="align-items: flex-start;">
                    <input type="checkbox" id="course-${index}" class="selection-checkbox" checked style="margin-top: 4px;">
                    <label for="course-${index}">
                        <strong>${escapeHtml(course.code || '')}</strong>: ${escapeHtml(course.name)}
                        <span style="display:block; font-size:0.85rem; color:var(--text-muted); margin-top:4px;">
                            Instructor: ${escapeHtml(course.instructor || 'Not provided')}
                        </span>
                    </label>
                </div>
                <div class="selection-right">
                    ${escapeHtml(course.exam_date)}
                </div>
            </div>
        `;
    });

    const cardId = 'course-card-' + Date.now();
    const cardHtml = `
        <div class="inline-card" id="${cardId}">
            <h4>Extracted Courses</h4>
            <div class="selection-list">
                ${listHtml}
            </div>
            <button class="btn btn-primary" onclick="confirmCourses('${cardId}')">Confirm Selection</button>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}

window.confirmCourses = function(cardId) {
    const card = document.getElementById(cardId);
    if(card) {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if(btn) btn.textContent = "Confirmed ✓";
        
        // Update state based on checks
        const checkboxes = card.querySelectorAll('.selection-checkbox');
        checkboxes.forEach((cb, idx) => {
            if(studyContext.courses[idx]) {
                studyContext.courses[idx].selected = cb.checked;
            }
        });
        updateContextSummary();
    }
    
    appendMessage('user', "I have confirmed my course selection.");
    
    // Simulate processing
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Fetching topics and materials... ⏳</span>`);
    
    setTimeout(() => {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        showTopicsAndResources();
    }, 1200);
}

// ----------------------------------------------------
// UI Flow: Step 2 - Topics & Materials Request
// ----------------------------------------------------
function showTopicsAndResources() {
    const data = demoData.gemma_topics;
    appendMessage('assistant', escapeHtml(data.reply));

    const uniqueCourses = [...new Set(data.topics.map(t => t.course))];
    let topicsHtml = '';
    
    uniqueCourses.forEach(course => {
        const courseTopics = data.topics.map((t, i) => ({...t, index: i})).filter(t => t.course === course);
        
        topicsHtml += `
            <div style="margin-bottom: 16px;">
                <h6 style="color: var(--indigo-dark); margin-bottom: 8px; font-size: 0.95rem;">${escapeHtml(course)}</h6>
                <div class="selection-list" style="margin-bottom: 0;">
        `;
        courseTopics.forEach(t => {
            topicsHtml += `
                <div class="selection-item" style="padding: 8px 12px;">
                    <div class="selection-left">
                        <input type="checkbox" id="topic-${t.index}" class="selection-checkbox" ${t.included ? 'checked' : ''}>
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
                        <span style="font-size:1.2rem;">📁</span> Upload Syllabus/PPTs (Select multiple)
                        <input type="file" id="file-input-${i}" class="hidden" accept=".pdf,.ppt,.pptx" multiple onchange="handleCourseUpload(${i}, ${uniqueCourses.length})">
                    </label>
                </div>
                
                <div id="uploaded-file-display-${i}" class="hidden" style="margin-bottom: 12px; padding: 10px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 6px; color: #0369a1; font-size: 0.9rem; font-weight: 600; display: flex; justify-content: space-between; align-items: center;">
                    <span id="uploaded-file-text-${i}"></span>
                    <button class="btn btn-outline btn-sm" style="background: white; padding: 4px 8px; font-size: 0.8rem; border-color: #bae6fd; color: #0369a1;" onclick="discardCourseUpload(${i}, ${uniqueCourses.length})">Discard</button>
                </div>

                <div style="display:flex; align-items:center; gap:6px;">
                    <input type="checkbox" id="req-video-${i}" checked style="width:14px;height:14px;">
                    <label for="req-video-${i}" style="font-size: 0.85rem; color: var(--text-main);">Request video explanations (YouTube/NPTEL)</label>
                </div>
                
                <button id="skip-btn-${i}" class="btn btn-outline btn-sm mt-3" style="width:100%; border-color:#cbd5e1; color:#64748b;" onclick="handleCourseUpload(${i}, ${uniqueCourses.length}, true)">Skip Upload</button>
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

window.handleCourseUpload = function(currentIndex, totalCourses, isSkip = false) {
    if (!isSkip) {
        const fileInput = document.getElementById(`file-input-${currentIndex}`);
        if (fileInput && fileInput.files.length > 0) {
            const filesList = Array.from(fileInput.files).map(f => `<strong>${escapeHtml(f.name)}</strong>`).join(', ');
            const textEl = document.getElementById(`uploaded-file-text-${currentIndex}`);
            const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
            const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
            const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);
            
            if (displayEl && textEl) {
                textEl.innerHTML = `✓ Uploaded: ${filesList}`;
                displayEl.classList.remove('hidden');
                displayEl.style.background = '#e0f2fe';
                displayEl.style.borderColor = '#bae6fd';
                displayEl.style.color = '#0369a1';
            }
            if (uploadArea) uploadArea.classList.add('hidden');
            if (skipBtn) skipBtn.classList.add('hidden');
        }
    } else {
        const textEl = document.getElementById(`uploaded-file-text-${currentIndex}`);
        const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
        const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
        const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);
        
        if (displayEl && textEl) {
            textEl.innerHTML = `<em>No file uploaded.</em>`;
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
}

window.discardCourseUpload = function(currentIndex, totalCourses) {
    const fileInput = document.getElementById(`file-input-${currentIndex}`);
    if (fileInput) fileInput.value = '';
    
    const displayEl = document.getElementById(`uploaded-file-display-${currentIndex}`);
    const uploadArea = document.getElementById(`upload-area-${currentIndex}`);
    const skipBtn = document.getElementById(`skip-btn-${currentIndex}`);
    
    if (displayEl) displayEl.classList.add('hidden');
    if (uploadArea) uploadArea.classList.remove('hidden');
    if (skipBtn) skipBtn.classList.remove('hidden');
    
    checkAllUploadsComplete(totalCourses);
}

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

window.submitMaterials = function(cardId) {
    const card = document.getElementById(cardId);
    if(card) {
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        const btn = card.querySelector('button');
        if(btn) btn.textContent = "Analyzing... ✓";
    }
    
    appendMessage('user', "I have uploaded my course materials.");
    
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Curating videos from YouTube and NPTEL... ⏳</span>`);
    
    setTimeout(() => {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        showCuratedMaterials();
    }, 1500);
}

// ----------------------------------------------------
// UI Flow: Step 3 - Curated Materials & Constraints
// ----------------------------------------------------
function showCuratedMaterials() {
    const materials = demoData.gemma_materials;
    appendMessage('assistant', escapeHtml(materials.reply));

    let videosHtml = '';
    materials.videos.forEach(v => {
        const badgeClass = v.platform === 'YouTube' ? 'badge-youtube' : 'badge-nptel';
        const icon = v.platform === 'YouTube' ? '▶️' : '🎓';
        videosHtml += `
            <div class="video-item">
                <div class="video-icon">${icon}</div>
                <div>
                    <a href="${escapeHtml(v.url)}" target="_blank" class="video-title">${escapeHtml(v.title)}</a>
                    <span class="video-meta"><span class="${badgeClass}">${escapeHtml(v.platform)}</span> Curated for you</span>
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
                Add any personal rules for Gemma (e.g. "won't study at night", "want to play in evening").
            </p>
            <div class="chat-input-wrapper" style="margin-bottom: 16px;">
                <textarea id="constraints-input-${cardId}" rows="2" placeholder="Type constraints here..."></textarea>
            </div>

            <button class="btn btn-primary w-full" onclick="generateRoadmap('${cardId}')">Build My Final Roadmap</button>
        </div>
    `;
    
    appendCustomCard(cardHtml);
}


window.generateRoadmap = function(cardId) {
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
    
    let msg = "Generate my roadmap.";
    if (constraints) {
        msg += `\nMy constraints: "${constraints}"`;
    }
    appendMessage('user', msg);
    
    const loadingId = 'loading-' + Date.now();
    appendMessage('assistant', `<span id="${loadingId}">Synthesizing plan constraints... ⏳</span>`);
    
    setTimeout(() => {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.parentElement.parentElement.remove();
        showRoadmap();
    }, 1500);
}

// ----------------------------------------------------
// UI Flow: Step 4 - Final Roadmap
// ----------------------------------------------------
function showRoadmap() {
    const planner = demoData.gemma_planner;
    appendMessage('assistant', escapeHtml(planner.reply));

    // TIMELINE VIEW
    let timelineHtml = '<div class="timeline">';
    planner.study_plan.forEach(day => {
        let details = '';
        day.blocks.forEach(b => {
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

    // SCHEDULE VIEW (Premium Layout)
    let scheduleHtml = '';
    planner.study_plan.forEach(day => {
        let blocksHtml = '';
        day.blocks.forEach(b => {
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
                            <span class="block-course">${escapeHtml(b.course || 'Flex Time')}</span>
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
                <h4 style="border-bottom:none; margin:0; padding:0;">Study Roadmap</h4>
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
}
