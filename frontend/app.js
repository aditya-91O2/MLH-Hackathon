document.addEventListener('DOMContentLoaded', () => {
    console.log("Study Planner initialized (Phase 3 Frontend)");
    initChat();
    initPrint();
});

// State
let chatHistory = [];
let studyContext = {
    courses: [],
    study_hours: null,
    start_date: null
};

// DOM
const chatHistoryEl = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatAttach = document.getElementById('chat-attach');
const attachLabel = document.getElementById('attach-label');
const chatError = document.getElementById('chat-error');

const coursesCard = document.getElementById('courses-card');
const coursesBody = document.getElementById('courses-body');
const addCourseBtn = document.getElementById('add-course-btn');
const summaryCourseCount = document.getElementById('summary-course-count');
const summaryStudyHours = document.getElementById('summary-study-hours');
const summaryStartDate = document.getElementById('summary-start-date');

// Utility to escape HTML
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe.toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// Image processing
function processImage(file) {
    return new Promise((resolve, reject) => {
        const allowedTypes = ['image/png', 'image/jpeg', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            return reject(new Error('Invalid image type. Only PNG, JPEG, and WebP are allowed.'));
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const maxWidth = 1500;
                let width = img.width;
                let height = img.height;
                if (width > maxWidth) {
                    height = Math.round((height * maxWidth) / width);
                    width = maxWidth;
                }
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                const base64Data = canvas.toDataURL(file.type).split(',')[1];
                resolve({ mime: file.type, data: base64Data });
            };
            img.onerror = () => reject(new Error('Failed to parse image file.'));
            img.src = e.target.result;
        };
        reader.onerror = () => reject(new Error('Failed to read file.'));
        reader.readAsDataURL(file);
    });
}

function updateContextSummary() {
    summaryCourseCount.textContent = studyContext.courses.length;
    summaryStudyHours.textContent = studyContext.study_hours || 'Pending';
    summaryStartDate.textContent = studyContext.start_date || 'Pending';
}

function renderCoursesTable() {
    coursesBody.innerHTML = '';
    if (studyContext.courses.length > 0) {
        coursesCard.classList.remove('hidden');
    } else {
        coursesCard.classList.add('hidden');
    }
    
    studyContext.courses.forEach((course, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" class="course-name" value="${escapeHtml(course.name || '')}"></td>
            <td><input type="date" class="course-date" value="${escapeHtml(course.exam_date || '')}"></td>
            <td><input type="number" class="course-credits" min="1" max="10" placeholder="Credits" value="${escapeHtml(course.credits || '')}"></td>
            <td><button class="btn btn-danger btn-sm delete-course-btn">Del</button></td>
        `;
        
        const updateState = () => {
            course.name = tr.querySelector('.course-name').value;
            course.exam_date = tr.querySelector('.course-date').value;
            course.credits = tr.querySelector('.course-credits').value;
            updateContextSummary();
        };

        tr.querySelector('.course-name').addEventListener('input', updateState);
        tr.querySelector('.course-date').addEventListener('input', updateState);
        tr.querySelector('.course-credits').addEventListener('input', updateState);
        
        tr.querySelector('.delete-course-btn').addEventListener('click', () => {
            studyContext.courses.splice(index, 1);
            renderCoursesTable();
            updateContextSummary();
        });
        
        coursesBody.appendChild(tr);
    });
}

addCourseBtn.addEventListener('click', () => {
    studyContext.courses.push({ name: '', exam_date: '', credits: '' });
    renderCoursesTable();
    updateContextSummary();
});

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = `<p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>`;
    chatHistoryEl.appendChild(msgDiv);
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
    
    if (role === 'user' || role === 'assistant') {
        chatHistory.push({ role, content: text });
    }
}

function mergeExtractedData(data) {
    if (data.courses && Array.isArray(data.courses)) {
        data.courses.forEach(newCourse => {
            if (!newCourse.name && !newCourse.exam_date) return;
            const existing = studyContext.courses.find(c => 
                (c.name || '').toLowerCase() === (newCourse.name || '').toLowerCase()
            );
            if (existing) {
                if (newCourse.exam_date && !existing.exam_date) existing.exam_date = newCourse.exam_date;
            } else {
                studyContext.courses.push({
                    name: newCourse.name || '',
                    exam_date: newCourse.exam_date || '',
                    credits: ''
                });
            }
        });
    }
    if (data.study_hours) studyContext.study_hours = data.study_hours;
    if (data.start_date) studyContext.start_date = data.start_date;
}

function initChat() {
    chatAttach.addEventListener('change', () => {
        if (chatAttach.files.length > 0) {
            attachLabel.textContent = chatAttach.files[0].name;
        } else {
            attachLabel.textContent = '';
        }
    });

    chatSend.addEventListener('click', async () => {
        const text = chatInput.value.trim();
        const file = chatAttach.files[0];
        
        if (!text && !file) return;
        
        let userMsgText = text;
        if (file) userMsgText += (text ? "\n" : "") + `[Attached: ${file.name}]`;
        appendMessage('user', userMsgText);
        
        chatInput.value = '';
        chatAttach.value = '';
        attachLabel.textContent = '';
        
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'message assistant loading';
        loadingMsg.innerHTML = '<p>Thinking...</p>';
        chatHistoryEl.appendChild(loadingMsg);
        chatSend.disabled = true;
        chatError.classList.add('hidden');
        
        try {
            let imageData = null;
            if (file && file.type.startsWith('image/')) {
                imageData = await processImage(file);
            } else if (file && file.name.endsWith('.txt')) {
                const txt = await file.text();
                chatHistory[chatHistory.length - 1].content += `\n\n--- File Content ---\n${txt}`;
            }
            
            const payload = {
                messages: chatHistory.slice(-10), // Send last 10 messages for context
                context: studyContext,
            };
            if (imageData) payload.image = imageData;
            
            // Delegate API communication to the independent apiClient
            const data = await apiClient.sendConversation(payload);
            
            chatHistoryEl.removeChild(loadingMsg);
            
            if (data.extracted_data) {
                mergeExtractedData(data.extracted_data);
                renderCoursesTable();
                updateContextSummary();
            }

            if (data.reply) {
                appendMessage('assistant', data.reply);
            }
            
            // Graceful fallback for unknown fields outside the current contract
            const knownKeys = ['reply', 'extracted_data'];
            const unknownKeys = Object.keys(data).filter(k => !knownKeys.includes(k));
            if (unknownKeys.length > 0) {
                console.warn('Received unsupported fields from backend API contract:', unknownKeys);
            }
            
        } catch (e) {
            chatHistoryEl.removeChild(loadingMsg);
            chatError.textContent = "Error: " + e.message;
            chatError.classList.remove('hidden');
        } finally {
            chatSend.disabled = false;
        }
    });

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatSend.click();
        }
    });
}

function initPrint() {
    document.getElementById('print-btn').addEventListener('click', () => {
        window.print();
    });
}
