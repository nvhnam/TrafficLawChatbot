/**
 * db.js - Quản lý cơ sở dữ liệu IndexedDB cho ứng dụng Luật Giao Thông AI
 */

const DB_NAME = 'TrafficLawAI_DB';
const DB_VERSION = 1;

class TrafficLawDB {
    constructor() {
        this.db = null;
    }

    async init() {
        if (this.db) return this.db;
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                // Store lưu các phiên chat
                if (!db.objectStoreNames.contains('sessions')) {
                    db.createObjectStore('sessions', { keyPath: 'id' });
                }
                // Store lưu chi tiết tin nhắn
                if (!db.objectStoreNames.contains('messages')) {
                    const msgStore = db.createObjectStore('messages', { keyPath: 'id', autoIncrement: true });
                    msgStore.createIndex('sessionId', 'sessionId', { unique: false });
                }
            };

            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };

            request.onerror = () => reject(request.error);
        });
    }

    // --- SESSION METHODS ---
    async addSession(session) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['sessions'], 'readwrite');
            const store = transaction.objectStore('sessions');
            const request = store.put(session);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getAllSessions() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['sessions'], 'readonly');
            const store = transaction.objectStore('sessions');
            const request = store.getAll();
            request.onsuccess = () => {
                // Sắp xếp theo thời gian mới nhất lên đầu
                const sessions = request.result.sort((a, b) => b.timestamp - a.timestamp);
                resolve(sessions);
            };
            request.onerror = () => reject(request.error);
        });
    }

    async deleteSession(sessionId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['sessions', 'messages'], 'readwrite');
            
            // Xóa session
            transaction.objectStore('sessions').delete(sessionId);
            
            // Xóa tất cả tin nhắn thuộc session đó
            const msgStore = transaction.objectStore('messages');
            const index = msgStore.index('sessionId');
            const request = index.openKeyCursor(IDBKeyRange.only(sessionId));
            
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    msgStore.delete(cursor.primaryKey);
                    cursor.continue();
                }
            };

            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }

    // --- MESSAGE METHODS ---
    async addMessage(message) {
        await this.init();
        return new Promise(async (resolve, reject) => {
            const transaction = this.db.transaction(['messages'], 'readwrite');
            const store = transaction.objectStore('messages');
            
            // Lưu tin nhắn mới
            const addRequest = store.add(message);
            
            addRequest.onsuccess = async () => {
                // Kiểm tra giới hạn 30 tin cho session này
                const index = store.index('sessionId');
                const countRequest = index.count(IDBKeyRange.only(message.sessionId));
                
                countRequest.onsuccess = () => {
                    if (countRequest.result > 30) {
                        // Tìm và xóa tin nhắn cũ nhất của session này
                        const cursorRequest = index.openCursor(IDBKeyRange.only(message.sessionId));
                        cursorRequest.onsuccess = (e) => {
                            const cursor = e.target.result;
                            if (cursor) {
                                store.delete(cursor.primaryKey);
                                // Chỉ xóa 1 tin cũ nhất (tin nhắn mới vừa được thêm nên count là 31)
                            }
                        };
                    }
                };
                resolve(addRequest.result);
            };
            
            addRequest.onerror = () => reject(addRequest.error);
        });
    }

    async getMessagesBySession(sessionId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['messages'], 'readonly');
            const store = transaction.objectStore('messages');
            const index = store.index('sessionId');
            const request = index.getAll(IDBKeyRange.only(sessionId));
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
}

// Khởi tạo instance duy nhất
window.chatDB = new TrafficLawDB();
