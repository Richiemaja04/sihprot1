// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000/api';
const WS_BASE_URL = 'ws://127.0.0.1:8000/ws';

// Global API instance
class API {
    constructor() {
        this.baseURL = API_BASE_URL;
        this.token = localStorage.getItem('auth_token');
        this.userType = localStorage.getItem('user_type');
        this.userId = localStorage.getItem('user_id');
        this.wsConnection = null;
        this.wsRetryCount = 0;
        this.maxWSRetries = 5;
    }

    // HTTP request wrapper with error handling
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const defaultHeaders = {
            'Content-Type': 'application/json',
        };

        if (this.token) {
            defaultHeaders.Authorization = `Bearer ${this.token}`;
        }

        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...options.headers,
            },
        };

        try {
            showLoading();
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: `HTTP ${response.status}: ${response.statusText}` 
                }));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json().catch(() => ({}));
            return data;
        } catch (error) {
            console.error('API Error:', error);
            showNotification(error.message, 'error');
            throw error;
        } finally {
            hideLoading();
        }
    }

    // Auth Methods
    async login(email, password, userType) {
        console.log('Attempting login:', { email, userType, url: `${this.baseURL}/auth/login` });
        
        // Method 1: Try with JSON first
        try {
            const response = await fetch(`${this.baseURL}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: email,
                    password: password
                })
            });

            if (response.ok) {
                const data = await response.json();
                return this.handleLoginSuccess(data);
            }
        } catch (error) {
            console.log('JSON login failed, trying form data...', error);
        }

        // Method 2: Fallback to form data
        try {
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const response = await fetch(`${this.baseURL}/auth/login`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: 'Login failed' 
                }));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            return this.handleLoginSuccess(data);
        } catch (error) {
            console.error('Both login methods failed:', error);
            throw error;
        }
    }

    handleLoginSuccess(data) {
        if (data.access_token) {
            this.token = data.access_token;
            this.userType = data.user_type;
            this.userId = data.employee_id || data.user_name;
            
            localStorage.setItem('auth_token', this.token);
            localStorage.setItem('user_type', this.userType);
            localStorage.setItem('user_id', this.userId);
            localStorage.setItem('user_name', data.user_name);
            
            // Establish WebSocket connection
            this.connectWebSocket();
            
            console.log('Login successful:', { 
                userType: this.userType, 
                userName: data.user_name 
            });
        }
        return data;
    }

    async logout() {
        try {
            await this.request('/auth/logout', { method: 'POST' });
        } catch (error) {
            console.warn('Logout request failed:', error);
        } finally {
            this.token = null;
            this.userType = null;
            this.userId = null;
            
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_type');
            localStorage.removeItem('user_id');
            localStorage.removeItem('user_name');
            
            if (this.wsConnection) {
                this.wsConnection.close();
            }
            
            window.location.href = '/';
        }
    }

    async getCurrentUser() {
        return await this.request('/auth/me');
    }

    async testConnection() {
        try {
            const response = await fetch(`${this.baseURL}/auth/test`);
            return response.ok;
        } catch (error) {
            console.error('Connection test failed:', error);
            return false;
        }
    }

    // Student Methods
    async getPrograms() {
        return await this.request('/student/programs');
    }

    async getSemesters(department, level) {
        return await this.request(`/student/semesters/${encodeURIComponent(department)}/${encodeURIComponent(level)}`);
    }

    async getBatchInfo(department, level, semester) {
        return await this.request(`/student/batch-info/${encodeURIComponent(department)}/${encodeURIComponent(level)}/${encodeURIComponent(semester)}`);
    }

    async getStudentTimetable(department, level, semester) {
        return await this.request(`/student/timetable/${encodeURIComponent(department)}/${encodeURIComponent(level)}/${encodeURIComponent(semester)}`);
    }

    async getTimetableGrid(department, level, semester) {
        return await this.request(`/student/timetable-grid/${encodeURIComponent(department)}/${encodeURIComponent(level)}/${encodeURIComponent(semester)}`);
    }

    async getBatchSubjects(department, level, semester) {
        return await this.request(`/student/subjects/${encodeURIComponent(department)}/${encodeURIComponent(level)}/${encodeURIComponent(semester)}`);
    }

    async getFacultyInfo(facultyId) {
        return await this.request(`/student/faculty-info/${encodeURIComponent(facultyId)}`);
    }

    async getRoomInfo(roomId) {
        return await this.request(`/student/room-info/${encodeURIComponent(roomId)}`);
    }

    async searchTimetable(query, department = null, level = null, semester = null) {
        const params = new URLSearchParams({ query });
        if (department) params.append('department', department);
        if (level) params.append('level', level);
        if (semester) params.append('semester', semester);
        
        return await this.request(`/student/search?${params}`);
    }

    async getSystemStats() {
        return await this.request('/student/stats');
    }

    // Teacher Methods
    async getMyTimetable() {
        return await this.request('/teacher/my-timetable');
    }

    async getWorkloadSummary() {
        return await this.request('/teacher/workload-summary');
    }

    async requestLeave(leaveData) {
        return await this.request('/teacher/request-leave', {
            method: 'POST',
            body: JSON.stringify(leaveData),
        });
    }

    async getMyLeaveRequests() {
        return await this.request('/teacher/my-leave-requests');
    }

    async getAvailableSubstitutes() {
        return await this.request('/teacher/available-substitutes');
    }

    async cancelLeaveRequest(leaveId) {
        return await this.request(`/teacher/cancel-leave/${leaveId}`, {
            method: 'DELETE',
        });
    }

    async checkScheduleConflicts() {
        return await this.request('/teacher/schedule-conflicts');
    }

    async getTeachingAnalytics() {
        return await this.request('/teacher/teaching-analytics');
    }

    async submitFeedback(feedbackData) {
        return await this.request('/teacher/feedback', {
            method: 'POST',
            body: JSON.stringify(feedbackData),
        });
    }

    // Admin Methods
    async uploadFile(fileType, file) {
        const formData = new FormData();
        formData.append('file', file);

        return await this.request(`/admin/upload-${fileType}`, {
            method: 'POST',
            body: formData,
            headers: {}, // Remove Content-Type for FormData
        });
    }

    async generateTimetables(requestData) {
        return await this.request('/admin/generate-timetables', {
            method: 'POST',
            body: JSON.stringify(requestData),
        });
    }

    async getTimetableVersions() {
        return await this.request('/admin/timetable-versions');
    }

    async approveTimetable(versionId) {
        return await this.request(`/admin/approve-timetable/${versionId}`, {
            method: 'POST',
        });
    }

    async publishTimetable(versionId) {
        return await this.request(`/admin/publish-timetable/${versionId}`, {
            method: 'POST',
        });
    }

    async deleteTimetableVersion(versionId) {
        return await this.request(`/admin/timetable-version/${versionId}`, {
            method: 'DELETE',
        });
    }

    async getOptimizationLogs() {
        return await this.request('/admin/optimization-logs');
    }

    async getAdminSystemStats() {
        return await this.request('/admin/system-stats');
    }

    async createTeacherAccounts() {
        return await this.request('/auth/create-teacher-accounts', {
            method: 'POST',
        });
    }

    // WebSocket Methods
    connectWebSocket() {
        if (!this.userType || !this.userId) return;

        const wsUrl = `${WS_BASE_URL}/${this.userType}/${this.userId}`;
        
        try {
            this.wsConnection = new WebSocket(wsUrl);

            this.wsConnection.onopen = () => {
                console.log('WebSocket connected');
                this.wsRetryCount = 0;
                showNotification('Connected to real-time updates', 'success');
            };

            this.wsConnection.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.warn('Invalid WebSocket message:', event.data);
                }
            };

            this.wsConnection.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                
                // Retry connection if not intentionally closed
                if (event.code !== 1000 && this.wsRetryCount < this.maxWSRetries) {
                    this.wsRetryCount++;
                    setTimeout(() => {
                        console.log(`Retrying WebSocket connection (${this.wsRetryCount}/${this.maxWSRetries})`);
                        this.connectWebSocket();
                    }, 5000 * this.wsRetryCount);
                }
            };

            this.wsConnection.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

        } catch (error) {
            console.error('Failed to establish WebSocket connection:', error);
        }
    }

    handleWebSocketMessage(data) {
        const { type, message } = data;

        switch (type) {
            case 'connection_established':
                console.log('WebSocket connection confirmed');
                break;
                
            case 'timetable_updated':
                showNotification(message, 'info');
                // Refresh timetable if currently viewing
                if (window.location.pathname.includes('timetable')) {
                    window.location.reload();
                }
                break;
                
            case 'generation_complete':
                showNotification(message, 'success');
                // Trigger refresh of timetable versions for admin
                if (this.userType === 'admin') {
                    window.dispatchEvent(new CustomEvent('timetableGenerationComplete', { detail: data }));
                }
                break;
                
            case 'generation_error':
                showNotification(message, 'error');
                break;
                
            case 'optimization_progress':
                // Update progress indicators
                window.dispatchEvent(new CustomEvent('optimizationProgress', { detail: data }));
                break;
                
            case 'teacher_leave_update':
                showNotification(message, 'info');
                break;
                
            case 'room_change_complete':
                showNotification(message, 'info');
                break;
                
            case 'emergency_update':
                showNotification(message, 'warning');
                break;
                
            case 'system_maintenance':
                showNotification('System maintenance scheduled: ' + message, 'warning');
                break;
                
            case 'heartbeat':
                // Keep connection alive
                break;
                
            default:
                console.log('Unknown WebSocket message type:', type);
        }
    }

    sendWebSocketMessage(message) {
        if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
            this.wsConnection.send(JSON.stringify(message));
        }
    }

    // File upload with progress
    async uploadFileWithProgress(endpoint, file, progressCallback) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();
            formData.append('file', file);

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    if (progressCallback) progressCallback(percentComplete);
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (error) {
                        reject(new Error('Invalid response format'));
                    }
                } else {
                    try {
                        const errorResponse = JSON.parse(xhr.responseText);
                        reject(new Error(errorResponse.detail || `HTTP ${xhr.status}`));
                    } catch (error) {
                        reject(new Error(`HTTP ${xhr.status}`));
                    }
                }
            };

            xhr.onerror = () => {
                reject(new Error('Network error'));
            };

            xhr.open('POST', `${this.baseURL}${endpoint}`);
            if (this.token) {
                xhr.setRequestHeader('Authorization', `Bearer ${this.token}`);
            }
            xhr.send(formData);
        });
    }
}

// Global API instance
const api = new API();

// Utility functions for loading and notifications
function showLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.add('active');
    }
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notificationContainer');
    if (!container) {
        console.log(`Notification (${type}): ${message}`);
        return;
    }

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(notification);

    // Auto remove notification
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => {
            if (container.contains(notification)) {
                container.removeChild(notification);
            }
        }, 300);
    }, duration);

    // Click to dismiss
    notification.addEventListener('click', () => {
        notification.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => {
            if (container.contains(notification)) {
                container.removeChild(notification);
            }
        }, 300);
    });
}

function getNotificationIcon(type) {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Test API connection on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const isConnected = await api.testConnection();
        if (!isConnected) {
            showNotification('Backend connection failed. Please check if the server is running.', 'error');
        }
    } catch (error) {
        console.warn('Could not test API connection:', error);
    }
});

// Export for use in other files
window.api = api;