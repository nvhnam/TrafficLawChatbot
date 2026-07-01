// ==========================================
// KIỂM TRA ĐĂNG NHẬP & RENDER AVATAR (TRANG CHAT)
// ==========================================
const currentUserStr = localStorage.getItem('currentUser');
let currentUser = null;

if (!currentUserStr) {
    window.location.href = 'auth.html';
} else {
    currentUser = JSON.parse(currentUserStr);

    document.addEventListener('DOMContentLoaded', () => {
        const nameParts = currentUser.username.trim().split(' ');
        const lastWord = nameParts[nameParts.length - 1];
        const initial = lastWord.charAt(0).toUpperCase();

        const avatarBtn = document.getElementById('user-avatar-btn');
        if (avatarBtn) avatarBtn.innerText = initial;

        const displayUsername = document.getElementById('display-username');
        if (displayUsername) displayUsername.innerText = currentUser.username;

        const displayRole = document.getElementById('display-role');
        if (currentUser.role === 'admin') {
            if (displayRole) {
                displayRole.innerText = 'Quản trị viên';
                displayRole.classList.replace('text-amber-500', 'text-red-500');
            }
            if (avatarBtn) avatarBtn.classList.replace('bg-amber-600', 'bg-red-600');
            const adminLink = document.getElementById('admin-link');
            if (adminLink) adminLink.classList.remove('hidden');
        } else {
            if (displayRole) displayRole.innerText = 'Người dùng';
        }
    });
}

// ------------------------------------------
// CÁC HÀM XỬ LÝ MENU & ĐĂNG XUẤT
// ------------------------------------------
function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

document.addEventListener('click', function (event) {
    const dropdown = document.getElementById('user-dropdown');
    const avatarBtn = document.getElementById('user-avatar-btn');
    if (avatarBtn && dropdown && !avatarBtn.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.add('hidden');
    }
});

function logout() {
    localStorage.removeItem('currentUser');
    window.location.href = 'auth.html';
}

function toggleSidebarSettings() {
    const menu = document.getElementById('sidebar-settings-menu');
    const chevron = document.getElementById('sidebar-settings-chevron');

    if (menu && chevron) {
        if (menu.classList.contains('hidden')) {
            menu.classList.remove('hidden');
            menu.classList.add('flex');
            chevron.classList.add('rotate-180');
        } else {
            menu.classList.add('hidden');
            menu.classList.remove('flex');
            chevron.classList.remove('rotate-180');
        }
    }
}

// ==========================================
// LOGIC XỬ LÝ CHAT & LỊCH SỬ
// ==========================================
const input = document.getElementById('user-input');
const messages = document.getElementById('messages');
const welcome = document.getElementById('welcome-screen');
const imageUploadInput = document.getElementById('image-upload');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreview = document.getElementById('image-preview');

let selectedImageBase64 = null;
let messageCounter = 0;
let currentSessionId = null;

document.addEventListener('DOMContentLoaded', async () => {
    if (window.chatDB) await renderSidebar();
});

window.previewImage = function (event) {
    const file = event.target.files[0];
    if (file) processSelectedFile(file);
}

function processSelectedFile(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
        if (imagePreview) imagePreview.src = e.target.result;
        if (imagePreviewContainer) imagePreviewContainer.style.display = 'inline-block';
        selectedImageBase64 = e.target.result;

        const sendBtn = document.getElementById('send-btn');
        if (sendBtn) sendBtn.disabled = false;
        scrollToBottom();
    }
    reader.readAsDataURL(file);
}

function removeImage() {
    if (imageUploadInput) imageUploadInput.value = "";
    if (imagePreview) imagePreview.src = "";
    if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
    selectedImageBase64 = null;

    const sendBtn = document.getElementById('send-btn');
    if (sendBtn && input && input.value.trim() === '') {
        sendBtn.disabled = true;
    }
}

if (input) {
    const sendBtn = document.getElementById('send-btn');
    input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value.trim() !== '' || selectedImageBase64) {
            sendBtn.disabled = false;
        } else {
            sendBtn.disabled = true;
        }
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
            e.preventDefault();
            handleSend();
        }
    });
}

function backToHome() { createNewChat(); }

function createNewChat() {
    currentSessionId = null;
    if (welcome) welcome.classList.remove('hidden');
    if (messages) messages.innerHTML = '';
    if (input) {
        input.value = '';
        input.style.height = 'auto';
    }
    removeImage();
    const chatWin = document.getElementById('chat-window');
    if (chatWin) chatWin.scrollTo({ top: 0, behavior: 'smooth' });

    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
}

async function renderSidebar() {
    if (!window.chatDB) return;
    const sessions = await window.chatDB.getAllSessions();
    const sessionList = document.getElementById('session-list');
    if (!sessionList) return;
    sessionList.innerHTML = '';

    sessions.forEach(session => {
        const isActive = session.id === currentSessionId ? 'active' : '';
        const html = `
            <div class="session-item ${isActive}" onclick="loadChat('${session.id}')">
                <div class="flex items-center gap-3 overflow-hidden">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                    <span class="truncate">${session.title}</span>
                </div>
                <button class="delete-session" onclick="event.stopPropagation(); deleteChat('${session.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
        `;
        sessionList.insertAdjacentHTML('beforeend', html);
    });
}

async function loadChat(sessionId) {
    currentSessionId = sessionId;
    if (welcome) welcome.classList.add('hidden');
    if (messages) messages.innerHTML = '';

    if (window.chatDB) {
        const savedMessages = await window.chatDB.getMessagesBySession(sessionId);
        savedMessages.forEach(msg => {
            appendMessageUI(msg.role, msg.text, msg.imageUrl, false);
        });
        renderSidebar();
    }
    if (window.innerWidth < 768) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) sidebar.classList.remove('open');
    }
}

async function deleteChat(sessionId) {
    if (confirm('Bạn có chắc chắn muốn xóa cuộc trò chuyện này?')) {
        await window.chatDB.deleteSession(sessionId);
        if (currentSessionId === sessionId) createNewChat();
        renderSidebar();
    }
}

async function clearAllHistory() {
    if (confirm('Xóa TOÀN BỘ lịch sử chat? Thao tác này không thể hoàn tác.')) {
        const sessions = await window.chatDB.getAllSessions();
        for (const s of sessions) {
            await window.chatDB.deleteSession(s.id);
        }
        createNewChat();
        renderSidebar();
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.toggle('open');
}

window.quickSearch = function (query) {
    if (input) {
        input.value = query;
        const sendBtn = document.getElementById('send-btn');
        if (sendBtn) sendBtn.disabled = false;
        handleSend();
    }
}

async function handleSend() {
    const sendBtn = document.getElementById('send-btn');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    if (welcome && !welcome.classList.contains('hidden')) {
        welcome.classList.add('hidden');
    }

    if (!currentSessionId) {
        currentSessionId = 'session-' + Date.now();
        const firstWords = text.split(' ').slice(0, 5).join(' ') + (text.split(' ').length > 5 ? '...' : '');
        if (window.chatDB) {
            await window.chatDB.addSession({
                id: currentSessionId,
                title: firstWords || 'Cuộc trò chuyện mới',
                timestamp: Date.now()
            });
            renderSidebar();
        }
    }

    let historyForPayload = [];
    if (window.chatDB) {
        try {
            const fullHistory = await window.chatDB.getMessagesBySession(currentSessionId);
            const recentHistory = fullHistory.slice(-4);
            historyForPayload = recentHistory.map(msg => ({ role: msg.role, text: msg.text }));
        } catch (err) { }
    }

    const userMsg = {
        sessionId: currentSessionId,
        role: 'user',
        text: text,
        imageUrl: selectedImageBase64,
        timestamp: Date.now()
    };
    if (window.chatDB) await window.chatDB.addMessage(userMsg);

    appendMessageUI('user', text, selectedImageBase64);

    input.value = '';
    input.style.height = 'auto';
    if (sendBtn) sendBtn.disabled = true;

    const imageToSend = selectedImageBase64;
    removeImage();

    const botMsgId = appendMessageUI('bot', '');

    try {
        let response;
        const payload = {
            session_id: currentSessionId,
            current_question: text,
            history: historyForPayload
        };

        if (window.USE_MOCK) {
            response = window.getMockChatResponse(text);
        } else {
            if (imageToSend) {
                payload.image = imageToSend;
                response = await fetch('http://localhost:1904/answer_with_image_input', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'ngrok-skip-browser-warning': 'true'
                    },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await fetch('http://localhost:1904/chat_stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'ngrok-skip-browser-warning': 'true'
                    },
                    body: JSON.stringify(payload)
                });
            }
        }

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let botFullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                updateMessage(botMsgId, botFullText, false);
                break;
            }
            const chunkText = decoder.decode(value, { stream: true });
            let cleanText = chunkText.replace(/^data:\s*/gm, '');
            if (cleanText.endsWith('\n\n')) cleanText = cleanText.slice(0, -2);
            botFullText += cleanText;

            updateMessage(botMsgId, botFullText, true);
        }

        if (window.chatDB) {
            await window.chatDB.addMessage({
                sessionId: currentSessionId,
                role: 'bot',
                text: botFullText,
                timestamp: Date.now()
            });
        }
    } catch (error) {
        updateMessage(botMsgId, `❌ Lỗi kết nối API: ${error.message}`, false);
    }
}

function appendMessageUI(role, text, imageUrl = null, animate = true) {
    if (!messages) return;
    const id = 'msg-' + Date.now() + '-' + (messageCounter++);
    const botImageUrl = "./image/avt_bot.png";
    const avatar = role === 'user' ? '' : `<img src="${botImageUrl}" alt="Bot Avatar" class="bot-avatar-img">`;
    const imageHtml = imageUrl ? `<div class="mb-3"><img src="${imageUrl}" class="max-h-60 rounded-xl border border-gray-600 shadow-md" alt="Uploaded Image"></div>` : '';

    const html = `
        <div id="${id}" class="flex gap-4 ${role === 'user' ? 'justify-end' : ''} ${animate ? 'animate-fade-in' : ''} mb-6">
            ${avatar}
            <div class="${role === 'user' ? 'bg-[#303132] px-4 py-3 rounded-3xl max-w-[85%] w-fit' : 'flex-1'}">
                ${imageHtml}
                <div class="text-md leading-relaxed message-content text-gray-200">${role === 'bot' && text === '' ? '<span class="animate-pulse text-amber-500">Đang lục tìm Luật...</span>' : marked.parse(text)}</div>
            </div>
        </div>
    `;
    messages.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
    return id;
}

function updateMessage(id, newText, isStreaming = false) {
    const el = document.getElementById(id);
    if (!el) return;
    const msgContent = el.querySelector('.message-content');
    if (!msgContent) return;

    let formattedHTML = marked.parse(newText);
    if (isStreaming) {
        const cursor = '<span class="blinking-cursor">|</span>';
        const lastTagRegex = /(<\/(p|li|h[1-6])>)\s*$/;
        if (lastTagRegex.test(formattedHTML)) {
            formattedHTML = formattedHTML.replace(lastTagRegex, `${cursor}$1`);
        } else {
            formattedHTML += cursor;
        }
    }
    msgContent.innerHTML = formattedHTML;
    scrollToBottom();
}

function scrollToBottom() {
    const chatWindow = document.getElementById('chat-window');
    if (chatWindow) chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: 'smooth' });
}

// ==========================================
// KÉO THẢ ẢNH VÀO CHAT
// ==========================================
const dragOverlay = document.getElementById('drag-overlay');
let dragCounter = 0;

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    document.body.addEventListener(eventName, preventDefaults, false);
});
function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

['dragenter', 'dragover'].forEach(eventName => {
    document.body.addEventListener(eventName, highlight, false);
});
['dragleave', 'drop'].forEach(eventName => {
    document.body.addEventListener(eventName, unhighlight, false);
});

function highlight(e) {
    if (!dragOverlay) return;
    if (e.type === 'dragenter') dragCounter++;
    dragOverlay.classList.remove('hidden');
    dragOverlay.classList.add('flex');
}

function unhighlight(e) {
    if (!dragOverlay) return;
    if (e.type === 'dragleave') dragCounter--;
    if (dragCounter === 0 || e.type === 'drop') {
        dragOverlay.classList.add('hidden');
        dragOverlay.classList.remove('flex');
        dragCounter = 0;
    }
}

document.body.addEventListener('drop', handleDrop, false);
function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        const file = files[0];
        if (file.type.startsWith('image/')) {
            const fileInput = document.getElementById('image-upload');
            if (fileInput) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
            }
            processSelectedFile(file);
        } else {
            alert("Vui lòng chỉ thả tệp hình ảnh (JPG, PNG,...) vào đoạn chat!");
        }
    }
}