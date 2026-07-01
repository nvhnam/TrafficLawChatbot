// ==========================================
// KIỂM TRA QUYỀN ADMIN
// ==========================================
const currentUserStr = localStorage.getItem('currentUser');
if (!currentUserStr) {
    window.location.href = 'auth.html';
} else {
    const user = JSON.parse(currentUserStr);
    if (user.role !== 'admin') {
        window.location.href = 'index.html';
    }
}

// ------------------------------------------
// CÁC HÀM XỬ LÝ MENU ADMIN
// ------------------------------------------
function toggleAdminSettings() {
    const menu = document.getElementById('admin-settings-menu');
    if (menu) menu.classList.toggle('hidden');
}

document.addEventListener('click', function (event) {
    const menu = document.getElementById('admin-settings-menu');
    if (!menu) return;
    const btn = menu.previousElementSibling;
    if (btn && !btn.contains(event.target) && !menu.contains(event.target)) {
        menu.classList.add('hidden');
    }
});

function logout() {
    localStorage.removeItem('currentUser');
    window.location.href = 'auth.html';
}

// ==========================================
// LOGIC QUẢN LÝ TABS & API BẢNG THỐNG KÊ
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // Render admin user profile pill
    const user = JSON.parse(currentUserStr);
    const nameParts = user.username.trim().split(' ');
    const lastWord = nameParts[nameParts.length - 1];
    const initial = lastWord.charAt(0).toUpperCase();

    const avatarBtn = document.getElementById('user-avatar-btn');
    if (avatarBtn) {
        avatarBtn.innerText = initial;
        avatarBtn.className = 'w-8 h-8 bg-red-600 rounded-full flex items-center justify-center text-sm font-bold text-white uppercase';
    }

    const displayUsername = document.getElementById('display-username');
    if (displayUsername) displayUsername.innerText = user.username;

    const displayRole = document.getElementById('display-role');
    if (displayRole) {
        displayRole.innerText = 'Quản trị viên';
        displayRole.className = 'text-[10px] text-red-500 leading-none mt-1 font-semibold';
    }

    switchAdminTab('view');
});

function switchAdminTab(tabName) {
    const viewBtn = document.getElementById('tab-view-btn');
    const addBtn = document.getElementById('tab-add-btn');
    const viewContent = document.getElementById('tab-view-content');
    const addContent = document.getElementById('tab-add-content');

    if (!viewBtn || !addBtn || !viewContent || !addContent) return;

    if (tabName === 'view') {
        viewBtn.classList.replace('text-gray-400', 'text-amber-500');
        viewBtn.classList.replace('border-transparent', 'border-amber-500');
        addBtn.classList.replace('text-amber-500', 'text-gray-400');
        addBtn.classList.replace('border-amber-500', 'border-transparent');

        viewContent.classList.remove('hidden');
        addContent.classList.add('hidden');
        fetchSystemStatsAPI();
    } else {
        addBtn.classList.replace('text-gray-400', 'text-amber-500');
        addBtn.classList.replace('border-transparent', 'border-amber-500');
        viewBtn.classList.replace('text-amber-500', 'text-gray-400');
        viewBtn.classList.replace('border-amber-500', 'border-transparent');

        addContent.classList.remove('hidden');
        viewContent.classList.add('hidden');
    }
}

async function fetchSystemStatsAPI() {
    const container = document.getElementById('tab-view-content');
    if (!container) return;

    container.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-amber-500 space-y-3 py-20">
            <div class="animate-spin h-10 w-10 border-4 border-amber-500 border-t-transparent rounded-full"></div>
            <p class="animate-pulse font-medium">Đang truy xuất dữ liệu từ Neo4j...</p>
        </div>
    `;

    try {
        const response = await fetch('http://localhost:1904/get_system_stats', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            }
        });

        if (!response.ok) throw new Error("Lỗi mạng: " + response.status);

        const result = await response.json();
        const data = result.data;

        if (!data) throw new Error("Không nhận được dữ liệu từ hệ thống.");

        let html = `
            <div class="flex justify-between items-center bg-[#1e1f20] p-6 rounded-xl border border-gray-700 mb-6 shadow-md">
                <div>
                    <h3 class="text-2xl font-bold text-white">Kho dữ liệu Neo4j</h3>
                    <p class="text-gray-400 mt-1">Danh sách các văn bản luật đang được sử dụng để trả lời người dùng.</p>
                </div>
                <div class="flex gap-4">
                    <!-- Tổng số văn bản -->
                    <div class="flex flex-col bg-amber-900/30 border border-amber-500/50 text-amber-400 px-6 py-4 rounded-lg flex flex-col items-center min-w-[180px]">
                        <span class="text-[10px] flex-1 uppercase font-bold tracking-wider opacity-80 mb-1">Tổng số văn bản</span>
                        <span class="text-3xl font-black text-white">${data.danh_sach_van_ban ? data.danh_sach_van_ban.length : 0}</span>
                    </div>
                    <!-- Tổng số đoạn văn (Chunks) -->
                    <div class="flex flex-col bg-amber-900/30 border border-amber-500/50 text-amber-400 px-6 py-4 rounded-lg flex flex-col items-center min-w-[180px]">
                        <span class="text-[10px] uppercase font-bold tracking-wider opacity-80 mb-1">Tổng số đoạn văn (Chunks)</span>
                        <span class="text-3xl font-black">${data.tong_so_doan_van_ban.toLocaleString()}</span>
                    </div>
                </div>
            </div>
            <div class="bg-[#1e1f20] rounded-xl border border-gray-700 overflow-hidden shadow-md">
                <table class="w-full text-left text-sm text-gray-300 border-collapse">
                    <thead class="bg-[#2a2b2d] text-xs uppercase text-gray-400 border-b border-gray-700">
                        <tr>
                            <th class="px-6 py-4 font-semibold w-16 text-center border-r border-gray-700/50">STT</th>
                            <th class="px-6 py-4 font-semibold">Tên Văn Bản / Nghị Định</th>
                            <th class="px-6 py-4 font-semibold w-64 text-center border-l border-gray-700/50">Loại Văn Bản</th>
                            <th class="px-6 py-4 font-semibold w-32 text-center border-l border-gray-700/50">Thao tác</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-700/50">
        `;

        if (data.danh_sach_van_ban && data.danh_sach_van_ban.length > 0) {
            data.danh_sach_van_ban.forEach((doc, index) => {
                html += `
                    <tr class="hover:bg-[#303132] transition-colors">
                        <td class="px-6 py-4 text-center font-mono text-gray-500 border-r border-gray-700/50">${index + 1}</td>
                        <td class="px-6 py-4 font-medium text-gray-200 leading-relaxed">
                            <div class="flex items-center gap-3">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                ${doc.Ten_Van_Ban}
                            </div>
                        </td>
                        <td class="px-6 py-4 text-center border-l border-gray-700/50">
                            <span class="px-4 py-1.5 bg-gray-800 text-gray-300 rounded-full text-[11px] font-bold tracking-wider uppercase border border-gray-600">
                                ${doc.Loai_Van_Ban}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-center border-l border-gray-700/50 relative">
                            <button onclick="toggleActionMenu(event, ${index})" class="text-gray-400 hover:text-white p-1 hover:bg-[#303132] rounded-lg transition">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
                                </svg>
                            </button>
                            <div id="action-menu-${index}" class="hidden absolute right-4 mt-1 w-28 bg-[#1e1f20] border border-gray-700 rounded-xl shadow-xl z-20 overflow-hidden text-left animate-fade-in">
                                <button onclick="confirmDeleteDoc(event, '${doc.Ten_Van_Ban.replace(/'/g, "\\'")}')" class="w-full px-4 py-2.5 text-xs font-semibold text-red-400 hover:text-red-500 hover:bg-red-500/10 transition flex items-center gap-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                    Xóa
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            });
        } else {
            html += `<tr><td colspan="4" class="px-6 py-12 text-center text-gray-500 italic">Chưa có văn bản luật nào trong hệ thống.</td></tr>`;
        }

        html += `</tbody></table></div>`;
        container.innerHTML = html;

    } catch (error) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full text-red-500 space-y-3 py-20">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-14 w-14 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p class="font-medium text-xl">Lỗi kết nối API Flask</p>
                <p class="text-sm text-gray-400">${error.message}</p>
                <button onclick="fetchSystemStatsAPI()" class="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition border border-gray-600">Thử lại</button>
            </div>
        `;
    }
}

// ==========================================
// LOGIC THÊM LUẬT (QUÉT THƯ MỤC)
// ==========================================
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const fileListContainer = document.getElementById('file-list-container');
const fileList = document.getElementById('file-list');
const importBtn = document.getElementById('import-btn');
const statusContainer = document.getElementById('status-container');
const statusText = document.getElementById('status-text');
const statusIcon = document.getElementById('status-icon');

let selectedFiles = [];

if (dropzone) {
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-amber-500', 'bg-[#2a2b2d]');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('border-amber-500', 'bg-[#2a2b2d]');
    });

    dropzone.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-amber-500', 'bg-[#2a2b2d]');
        showStatus('processing', 'Đang quét dữ liệu trong thư mục...');

        const items = e.dataTransfer.items;
        let files = [];

        if (items) {
            const promises = [];
            for (let i = 0; i < items.length; i++) {
                const item = items[i].webkitGetAsEntry();
                if (item) promises.push(traverseFileTree(item, files));
            }
            await Promise.all(promises);
        } else {
            files = Array.from(e.dataTransfer.files);
        }
        processNewFiles(files);
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) processNewFiles(Array.from(e.target.files));
    });
}

function traverseFileTree(item, filesList) {
    return new Promise((resolve) => {
        if (item.isFile) {
            item.file((file) => {
                filesList.push(file);
                resolve();
            });
        } else if (item.isDirectory) {
            const dirReader = item.createReader();
            dirReader.readEntries(async (entries) => {
                const promises = [];
                for (let i = 0; i < entries.length; i++) {
                    promises.push(traverseFileTree(entries[i], filesList));
                }
                await Promise.all(promises);
                resolve();
            });
        } else {
            resolve();
        }
    });
}

function processNewFiles(files) {
    const allowedExtensions = ['.txt', '.md', '.pdf', '.jpg', '.jpeg', '.png'];

    const newFiles = files.filter(file => {
        const fileName = file.name.toLowerCase();
        if (fileName.startsWith('.')) return false;
        return allowedExtensions.some(ext => fileName.endsWith(ext)) || file.type.startsWith('image/');
    });

    if (newFiles.length === 0) {
        showStatus('error', 'Không tìm thấy tệp tin hợp lệ trong thư mục này.');
        return;
    }

    selectedFiles = [...selectedFiles, ...newFiles];
    renderFileList();
    if (statusContainer) statusContainer.classList.add('hidden');
}

function renderFileList() {
    if (!fileList || !fileListContainer) return;
    fileList.innerHTML = '';
    const countText = fileListContainer.querySelector('p');
    if (countText) countText.textContent = `Danh sách tệp tin (${selectedFiles.length})`;

    if (selectedFiles.length > 0) {
        fileListContainer.classList.remove('hidden');
        if (importBtn) importBtn.disabled = false;

        selectedFiles.forEach((file, index) => {
            const size = formatBytes(file.size);
            const displayPath = file.webkitRelativePath || file.name;

            const item = document.createElement('div');
            item.className = 'flex justify-between items-center p-3 bg-[#303132] rounded-lg border border-gray-700';
            item.innerHTML = `
                <div class="flex-1 min-w-0 pr-4">
                    <p class="text-sm font-medium text-gray-200 truncate" title="${displayPath}">${displayPath}</p>
                    <p class="text-xs text-gray-500 mt-1">${file.type || 'Document'} • ${size}</p>
                </div>
                <button onclick="removeFile(${index})" class="text-gray-500 hover:text-red-500 transition p-1">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                </button>
            `;
            fileList.appendChild(item);
        });
    } else {
        fileListContainer.classList.add('hidden');
        if (importBtn) importBtn.disabled = true;
    }
}

window.removeFile = function (index) {
    selectedFiles.splice(index, 1);
    renderFileList();
    if (selectedFiles.length === 0 && fileInput) fileInput.value = '';
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024, dm = decimals < 0 ? 0 : decimals, sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

if (importBtn) {
    importBtn.addEventListener('click', async () => {
        if (selectedFiles.length === 0) return;

        showStatus('processing', `Đang chuẩn bị gửi ${selectedFiles.length} tệp tin lên Server...`);
        importBtn.disabled = true;

        const formData = new FormData();
        selectedFiles.forEach(file => { formData.append('files', file); });

        let progressInterval;
        try {
            progressInterval = setInterval(async () => {
                try {
                    const res = await fetch('http://localhost:1904/check_progress', {
                        headers: {
                            'ngrok-skip-browser-warning': 'true'
                        }
                    });
                    const progressData = await res.json();

                    if (progressData.data && progressData.data.is_running) {
                        const p = progressData.data;
                        let phaseText = "";
                        if (p.phase === "extracting") phaseText = "Trích xuất JSON";
                        else if (p.phase === "uploading") phaseText = "Nạp Neo4j";
                        else if (p.phase === "building_graph") phaseText = "Build Graph";

                        showStatus('processing', `[${phaseText}] ${p.message} (${p.processed_files}/${p.total_files})`);
                    }
                } catch (e) { }
            }, 1500);

            const response = await fetch('http://localhost:1904/process_folder_and_build', {
                method: 'POST',
                headers: {
                    'ngrok-skip-browser-warning': 'true'
                },
                body: formData
            });

            clearInterval(progressInterval);
            const result = await response.json();

            if (response.ok && result.errorCode === "0") {
                showStatus('success', `Tuyệt vời! ${result.data.message}`);
                selectedFiles = [];
                renderFileList();
                if (fileInput) fileInput.value = '';
                fetchSystemStatsAPI();
            } else {
                throw new Error(result.errorMessage || "Lỗi không xác định từ Server");
            }
        } catch (error) {
            clearInterval(progressInterval);
            showStatus('error', `Lỗi: ${error.message}`);
            importBtn.disabled = false;
        }
    });
}

function showStatus(type, message) {
    if (!statusContainer || !statusText) return;
    statusContainer.classList.remove('hidden');
    const box = document.getElementById('status-box');

    if (type === 'processing') {
        if (box) box.className = 'flex items-center gap-3 p-4 rounded-xl border border-amber-700/50 bg-amber-900/20 text-amber-500';
        if (statusIcon) {
            statusIcon.classList.remove('hidden');
            statusIcon.className = 'animate-spin h-5 w-5 border-2 border-amber-500 border-t-transparent rounded-full';
        }
    } else if (type === 'success') {
        if (box) box.className = 'flex items-center gap-3 p-4 rounded-xl border border-green-700/50 bg-green-900/20 text-green-500';
        if (statusIcon) statusIcon.classList.add('hidden');
    } else {
        if (box) box.className = 'flex items-center gap-3 p-4 rounded-xl border border-red-700/50 bg-red-900/20 text-red-500';
        if (statusIcon) statusIcon.classList.add('hidden');
    }
    statusText.textContent = message;
}

// ==========================================
// 🔴 LOGIC XỬ LÝ XÓA VĂN BẢN (FRONTEND ONLY)
// ==========================================
let documentToDelete = null;

// Khai báo các hàm điều khiển lên đối tượng window để nút gọi trực tiếp từ HTML được rendered động
window.toggleActionMenu = function (event, index) {
    event.stopPropagation();

    // Đóng tất cả các menu 3 chấm khác đang mở
    document.querySelectorAll('[id^="action-menu-"]').forEach(menu => {
        if (menu.id !== `action-menu-${index}`) {
            menu.classList.add('hidden');
        }
    });

    const menu = document.getElementById(`action-menu-${index}`);
    if (menu) {
        menu.classList.toggle('hidden');
    }
};

window.confirmDeleteDoc = function (event, docName) {
    event.stopPropagation();
    documentToDelete = docName;

    // Đóng toàn bộ các menu 3 chấm đang mở
    document.querySelectorAll('[id^="action-menu-"]').forEach(menu => {
        menu.classList.add('hidden');
    });

    const modal = document.getElementById('delete-confirm-modal');
    const docNameEl = document.getElementById('delete-doc-name');
    if (modal && docNameEl) {
        docNameEl.textContent = docName;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
};

window.closeDeleteModal = function () {
    const modal = document.getElementById('delete-confirm-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
    documentToDelete = null;
};

// Đóng menu 3 chấm khi người dùng click ra ngoài bất kỳ đâu
document.addEventListener('click', () => {
    document.querySelectorAll('[id^="action-menu-"]').forEach(menu => {
        menu.classList.add('hidden');
    });
});

// Khởi tạo đăng ký sự kiện cho nút xóa an toàn với mọi tiến trình load DOM
function initDeleteEvents() {
    const btnDelete = document.getElementById('btn-confirm-delete');
    if (btnDelete) {
        // Tránh trùng lặp đăng ký sự kiện nếu gọi nhiều lần
        btnDelete.removeEventListener('click', executeDeleteDoc);
        btnDelete.addEventListener('click', executeDeleteDoc);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteEvents);
} else {
    initDeleteEvents();
}

// Hàm thực thi việc gọi API xóa gửi lên Backend Neo4j
async function executeDeleteDoc() {
    if (!documentToDelete) return;

    const btnDelete = document.getElementById('btn-confirm-delete');

    // Chuyển nút sang trạng thái loading
    if (btnDelete) {
        btnDelete.disabled = true;
        btnDelete.innerHTML = `
            <span class="flex items-center justify-center gap-2">
                <span class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                Đang xóa...
            </span>
        `;
    }

    try {
        // Gửi request POST tới API xóa thực tế của Backend
        const response = await fetch('http://localhost:1904/delete_document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true' // Đảm bảo bypass warning của ngrok
            },
            body: JSON.stringify({
                document_name: documentToDelete
            })
        });

        const result = await response.json();

        if (response.ok && result.errorCode === "0") {
            // Gọi lại hàm load dữ liệu để tự động làm mới giao diện
            fetchSystemStatsAPI();
        } else {
            throw new Error(result.errorMessage || "Không thể thực hiện xóa văn bản trên database.");
        }

    } catch (error) {
        console.error("Lỗi khi kết nối với API xóa:", error);
        alert(`Lỗi khi thực hiện xóa: ${error.message}`);
    } finally {
        if (btnDelete) {
            btnDelete.disabled = false;
            btnDelete.textContent = 'Xác nhận xóa';
        }
        closeDeleteModal();
    }
}