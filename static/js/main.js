// ClipMontage Frontend — v3.0
// SPA with Router, View Controllers, API Client
// Firebase Auth + WebSocket + Polling preserved

// ══════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════

let currentProjectId = null;
let websocket = null;
let selectedFile = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let pollingTimer = null;

// Firebase state
let firebaseApp = null;
let firebaseAuth = null;
let currentUser = null;
let idToken = null;
let firebaseEnabled = false;
let tokenRefreshTimer = null;

// Auth modal state
let authIsSignUp = false;

const WS_MAX_RECONNECT = 5;
const WS_INITIAL_BACKOFF = 1000;
const POLLING_INTERVAL = 5000;
const FETCH_TIMEOUT = 30000;

const BACKEND_URL = window.location.hostname === 'localhost'
    ? ''
    : 'https://movie-auto-editor-1.onrender.com';

// ══════════════════════════════════════════════════════════
// API CLIENT
// ══════════════════════════════════════════════════════════

function getAuthHeaders() {
    const headers = {};
    if (idToken) {
        headers['Authorization'] = `Bearer ${idToken}`;
    }
    const geminiKey = localStorage.getItem('gemini_api_key');
    if (geminiKey) {
        headers['X-Gemini-Api-Key'] = geminiKey;
    }
    return headers;
}

async function fetchWithTimeout(url, options = {}, timeout = FETCH_TIMEOUT) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    const fullUrl = url.startsWith('/api') ? BACKEND_URL + url : url;
    const authHeaders = getAuthHeaders();
    const mergedHeaders = { ...(options.headers || {}), ...authHeaders };

    try {
        const resp = await fetch(fullUrl, {
            ...options,
            headers: mergedHeaders,
            signal: controller.signal,
        });

        // On 401, refresh token and retry once
        if (resp.status === 401 && currentUser) {
            clearTimeout(timer);
            console.warn('Got 401, refreshing token and retrying...');
            idToken = await currentUser.getIdToken(true);
            const retryHeaders = { ...(options.headers || {}), ...getAuthHeaders() };
            const controller2 = new AbortController();
            const timer2 = setTimeout(() => controller2.abort(), timeout);
            try {
                return await fetch(fullUrl, {
                    ...options,
                    headers: retryHeaders,
                    signal: controller2.signal,
                });
            } finally {
                clearTimeout(timer2);
            }
        }

        return resp;
    } finally {
        clearTimeout(timer);
    }
}

const API = {
    async getProjects() {
        const resp = await fetchWithTimeout('/api/projects');
        if (!resp.ok) throw new Error('Failed to load projects');
        return resp.json();
    },

    async getProject(id) {
        const resp = await fetchWithTimeout(`/api/projects/${id}`);
        if (!resp.ok) throw new Error('Failed to load project');
        return resp.json();
    },

    async deleteProject(id) {
        const resp = await fetchWithTimeout(`/api/projects/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('Failed to delete project');
        return resp.json();
    },

    async getDashboardStats() {
        const resp = await fetchWithTimeout('/api/dashboard/stats');
        if (!resp.ok) throw new Error('Failed to load stats');
        return resp.json();
    },

    async uploadFile(formData) {
        return fetchWithTimeout('/api/processing/upload', {
            method: 'POST',
            body: formData,
        }, 120000);
    },

    async initiateGCSUpload(filename, contentType, name) {
        return fetchWithTimeout('/api/processing/upload/initiate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename,
                content_type: contentType || 'video/mp4',
                name: name || filename,
                upload_content_type: 'fps_montage',
            }),
        });
    },

    async completeGCSUpload(projectId, gcsObjectName) {
        return fetchWithTimeout('/api/processing/upload/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projectId,
                gcs_object_name: gcsObjectName,
            }),
        });
    },

    async startProcessing(projectId) {
        return fetchWithTimeout('/api/processing/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projectId,
                content_type: 'fps_montage',
            }),
        });
    },

    async getStatus(projectId) {
        return fetchWithTimeout(`/api/processing/status/${projectId}`);
    },

    async cancelProject(projectId) {
        return fetchWithTimeout(`/api/projects/${projectId}/cancel`, { method: 'POST' });
    },
};

// ══════════════════════════════════════════════════════════
// ROUTER
// ══════════════════════════════════════════════════════════

const Router = {
    currentView: null,

    navigate(viewName, opts = {}) {
        // Hide all app views inside content-area
        const appViews = ['dashboard', 'upload', 'processing', 'result', 'error'];
        appViews.forEach(v => {
            const el = document.getElementById(`view-${v}`);
            if (el) el.style.display = 'none';
        });

        // Show target view
        const target = document.getElementById(`view-${viewName}`);
        if (target) target.style.display = 'block';

        this.currentView = viewName;

        // Update page title
        const titleMap = {
            dashboard: 'Dashboard',
            upload: 'New Project',
            processing: 'Processing',
            result: 'Result',
            error: 'Error',
        };
        const pageTitle = document.getElementById('pageTitle');
        if (pageTitle) pageTitle.textContent = titleMap[viewName] || viewName;

        // Update sidebar active state
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewName);
        });

        // Close mobile sidebar
        closeMobileSidebar();

        // Run view init
        if (viewName === 'dashboard') DashboardView.init();
        if (viewName === 'upload') UploadView.init();
        if (viewName === 'processing') ProcessingView.init(opts);
        if (viewName === 'result') ResultView.init(opts);
    },
};

// ══════════════════════════════════════════════════════════
// LAYOUT HELPERS
// ══════════════════════════════════════════════════════════

function showLanding() {
    document.getElementById('view-landing').style.display = 'block';
    document.getElementById('view-loading').style.display = 'none';
    document.getElementById('app-shell').style.display = 'none';
}

function showApp() {
    document.getElementById('view-landing').style.display = 'none';
    document.getElementById('view-loading').style.display = 'none';
    document.getElementById('app-shell').style.display = 'flex';
    Router.navigate('dashboard');
}

function showLoading() {
    document.getElementById('view-landing').style.display = 'none';
    document.getElementById('view-loading').style.display = 'block';
    document.getElementById('app-shell').style.display = 'none';
}

function hideLoading() {
    document.getElementById('view-loading').style.display = 'none';
}

// Auth modal
function openAuthModal() {
    document.getElementById('auth-modal').style.display = 'flex';
    clearAuthError();
}

function closeAuthModal() {
    document.getElementById('auth-modal').style.display = 'none';
}

function toggleAuthMode() {
    authIsSignUp = !authIsSignUp;
    const title = document.getElementById('authModalTitle');
    const subtitle = document.getElementById('authModalSubtitle');
    const submitBtn = document.getElementById('emailSignInBtn');
    const toggleBtn = document.getElementById('authToggleBtn');

    if (authIsSignUp) {
        title.textContent = 'Sign Up';
        subtitle.textContent = 'Create an account to get started';
        submitBtn.textContent = 'Sign Up';
        toggleBtn.innerHTML = 'Already have an account? <strong>Sign In</strong>';
    } else {
        title.textContent = 'Sign In';
        subtitle.textContent = 'Sign in to start creating montages';
        submitBtn.textContent = 'Sign In';
        toggleBtn.innerHTML = "Don't have an account? <strong>Sign Up</strong>";
    }
    clearAuthError();
}

// Mobile sidebar
function openMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('active');
}

function closeMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
}

// Toast notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ══════════════════════════════════════════════════════════
// FIREBASE AUTH (preserved)
// ══════════════════════════════════════════════════════════

// Fallback Firebase config (public, non-secret values)
const FIREBASE_FALLBACK_CONFIG = {
    enabled: true,
    apiKey: 'AIzaSyA1w0t5mlM8bH0RHd1Dp6Ziins32_thAM0',
    authDomain: 'moviecutter.firebaseapp.com',
    projectId: 'moviecutter',
};

async function initFirebase() {
    try {
        let config;
        try {
            const resp = await fetch(BACKEND_URL + '/api/config/firebase');
            if (resp.ok && resp.headers.get('content-type')?.includes('application/json')) {
                config = await resp.json();
            }
        } catch (_) { /* backend not reachable */ }

        if (!config) {
            console.warn('Could not fetch Firebase config from backend, using fallback');
            config = FIREBASE_FALLBACK_CONFIG;
        }

        if (!config.enabled) {
            firebaseEnabled = false;
            hideLoading();
            showApp();
            return;
        }

        firebaseEnabled = true;

        await loadScript('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
        await loadScript('https://www.gstatic.com/firebasejs/10.12.0/firebase-auth-compat.js');

        firebaseApp = firebase.initializeApp({
            apiKey: config.apiKey,
            authDomain: config.authDomain,
            projectId: config.projectId,
        });
        firebaseAuth = firebase.auth();

        firebaseAuth.onAuthStateChanged(async (user) => {
            if (tokenRefreshTimer) {
                clearInterval(tokenRefreshTimer);
                tokenRefreshTimer = null;
            }

            hideLoading();

            if (user) {
                const wasLoggedIn = !!currentUser;
                currentUser = user;
                idToken = await user.getIdToken(true);
                updateUserUI(user);
                closeAuthModal();
                // Only navigate to dashboard on fresh login, not on token refresh
                if (!wasLoggedIn) showApp();

                tokenRefreshTimer = setInterval(async () => {
                    if (currentUser) {
                        try {
                            idToken = await currentUser.getIdToken(true);
                        } catch (e) {
                            console.warn('Token refresh failed:', e);
                        }
                    }
                }, 50 * 60 * 1000);
            } else {
                currentUser = null;
                idToken = null;
                showLanding();
            }
        });
    } catch (e) {
        console.error('Firebase init failed:', e);
        firebaseEnabled = false;
        hideLoading();
        showApp();
    }
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function updateUserUI(user) {
    const avatar = document.getElementById('userAvatar');
    const nameEl = document.getElementById('userName');
    if (nameEl) nameEl.textContent = user.displayName || user.email || 'User';
    if (avatar) {
        if (user.photoURL) {
            avatar.src = user.photoURL;
            avatar.style.display = 'block';
        } else {
            avatar.style.display = 'none';
        }
    }
}

// Auth actions
async function signInWithGoogle() {
    clearAuthError();
    try {
        const provider = new firebase.auth.GoogleAuthProvider();
        await firebaseAuth.signInWithPopup(provider);
    } catch (e) {
        showAuthError(e.message);
    }
}

async function handleEmailSubmit() {
    clearAuthError();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;
    try {
        if (authIsSignUp) {
            await firebaseAuth.createUserWithEmailAndPassword(email, password);
        } else {
            await firebaseAuth.signInWithEmailAndPassword(email, password);
        }
    } catch (e) {
        showAuthError(e.message);
    }
}

async function signOut() {
    stopPolling();
    if (websocket) {
        websocket.close();
        websocket = null;
    }
    currentProjectId = null;

    if (firebaseAuth) {
        await firebaseAuth.signOut();
    }
    currentUser = null;
    idToken = null;
}

function showAuthError(message) {
    const el = document.getElementById('authError');
    if (el) {
        el.style.display = 'block';
        el.textContent = message;
    }
}

function clearAuthError() {
    const el = document.getElementById('authError');
    if (el) el.style.display = 'none';
}

// ══════════════════════════════════════════════════════════
// SETTINGS
// ══════════════════════════════════════════════════════════

function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'flex';
    const input = document.getElementById('settingsGeminiKey');
    const saved = localStorage.getItem('gemini_api_key');
    if (input && saved) input.value = saved;
}

function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'none';
}

function saveSettings() {
    const input = document.getElementById('settingsGeminiKey');
    const status = document.getElementById('settingsStatus');
    const key = input ? input.value.trim() : '';
    if (key) {
        localStorage.setItem('gemini_api_key', key);
        if (status) {
            status.style.display = 'block';
            status.style.color = '#4ade80';
            status.textContent = 'API key saved. It will be used for video analysis.';
        }
    } else {
        if (status) {
            status.style.display = 'block';
            status.style.color = '#f87171';
            status.textContent = 'Please enter a valid API key.';
        }
    }
}

function clearSettings() {
    localStorage.removeItem('gemini_api_key');
    const input = document.getElementById('settingsGeminiKey');
    const status = document.getElementById('settingsStatus');
    if (input) input.value = '';
    if (status) {
        status.style.display = 'block';
        status.style.color = '#facc15';
        status.textContent = 'API key cleared. Server default will be used.';
    }
}

// ══════════════════════════════════════════════════════════
// DASHBOARD VIEW
// ══════════════════════════════════════════════════════════

const DashboardView = {
    async init() {
        try {
            // Load stats and projects in parallel
            const [stats, projects] = await Promise.all([
                API.getDashboardStats().catch(() => null),
                API.getProjects().catch(() => []),
            ]);

            if (stats) {
                document.getElementById('statTotal').textContent = stats.total_projects ?? 0;
                document.getElementById('statCompleted').textContent = stats.completed ?? 0;
                document.getElementById('statProcessing').textContent = stats.processing ?? 0;
                document.getElementById('statFailed').textContent = stats.failed ?? 0;
            }

            this.renderProjects(projects);
        } catch (e) {
            console.error('Dashboard load error:', e);
        }
    },

    renderProjects(projects) {
        const grid = document.getElementById('projectGrid');
        const empty = document.getElementById('emptyState');

        if (!projects || projects.length === 0) {
            grid.innerHTML = '';
            grid.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        empty.style.display = 'none';
        grid.style.display = 'grid';

        // Sort by created_at descending
        const sorted = [...projects].sort((a, b) =>
            new Date(b.created_at) - new Date(a.created_at)
        );

        grid.innerHTML = sorted.map(p => {
            const date = new Date(p.created_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric',
            });

            const progressHtml = (p.status === 'processing' && p.progress > 0)
                ? `<div class="project-progress"><div class="project-progress-fill" style="width:${p.progress}%"></div></div>`
                : '';

            return `
                <div class="project-card" data-id="${p.id}" data-status="${p.status}">
                    <div class="project-card-header">
                        <span class="project-card-name">${this.escapeHtml(p.name)}</span>
                        <span class="project-status status-${p.status}">${p.status}</span>
                    </div>
                    <div class="project-card-meta">
                        <span class="project-card-date">${date}</span>
                        <div class="project-card-actions">
                            <button class="project-delete-btn" data-delete-id="${p.id}" title="Delete">Delete</button>
                        </div>
                    </div>
                    ${progressHtml}
                </div>
            `;
        }).join('');

        // Bind click events
        grid.querySelectorAll('.project-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.classList.contains('project-delete-btn')) return;
                const id = card.dataset.id;
                const status = card.dataset.status;
                this.openProject(id, status);
            });
        });

        grid.querySelectorAll('.project-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteProject(btn.dataset.deleteId);
            });
        });
    },

    openProject(id, status) {
        currentProjectId = id;
        if (status === 'completed') {
            Router.navigate('result', { projectId: id });
        } else if (status === 'processing') {
            Router.navigate('processing', { projectId: id, resume: true });
        } else if (status === 'failed') {
            Router.navigate('error');
            document.getElementById('errorMessage').textContent = 'This project failed during processing.';
        }
    },

    async deleteProject(id) {
        if (!confirm('Delete this project?')) return;
        try {
            await API.deleteProject(id);
            showToast('Project deleted');
            this.init(); // refresh
        } catch (e) {
            showToast('Failed to delete project', 'error');
        }
    },

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

// ══════════════════════════════════════════════════════════
// UPLOAD VIEW
// ══════════════════════════════════════════════════════════

const UploadView = {
    init() {
        selectedFile = null;
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';

        const uploadArea = document.getElementById('uploadArea');
        const selectedFileDiv = document.getElementById('selectedFile');
        if (uploadArea) uploadArea.style.display = 'block';
        if (selectedFileDiv) selectedFileDiv.style.display = 'none';
    },

    setFile(file) {
        const validExtensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm'];
        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

        if (!validExtensions.includes(fileExt)) {
            showToast('Invalid file format. Supported: MP4, MKV, AVI, MOV, WebM', 'error');
            return;
        }

        const maxSize = 20 * 1024 * 1024 * 1024;
        if (file.size > maxSize) {
            showToast('File too large. Maximum size: 20 GB', 'error');
            return;
        }

        selectedFile = file;
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = formatFileSize(file.size);
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('selectedFile').style.display = 'block';
    },

    cancelFile() {
        selectedFile = null;
        document.getElementById('fileInput').value = '';
        document.getElementById('uploadArea').style.display = 'block';
        document.getElementById('selectedFile').style.display = 'none';
    },

    async upload() {
        if (!selectedFile) return;

        const uploadBtn = document.getElementById('uploadBtn');

        try {
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';

            // Try GCS chunked upload first; fall back to legacy if not configured
            const initiateResp = await API.initiateGCSUpload(
                selectedFile.name,
                selectedFile.type || 'video/mp4',
                selectedFile.name
            );

            if (initiateResp.status === 503) {
                // GCS not configured — use legacy direct upload
                await this._legacyUpload();
                return;
            }

            if (!initiateResp.ok) {
                const err = await initiateResp.json().catch(() => ({}));
                throw new Error(err.detail || 'Failed to initiate upload');
            }

            const { project_id, upload_url, gcs_object_name } = await initiateResp.json();
            currentProjectId = project_id;

            // Show progress bar
            const progressEl = document.getElementById('uploadProgress');
            if (progressEl) progressEl.style.display = 'block';

            // Resumable upload directly to GCS
            await this._resumableUpload(upload_url, selectedFile, (pct) => {
                const bar = document.getElementById('uploadProgressFill');
                const label = document.getElementById('uploadProgressLabel');
                if (bar) bar.style.width = `${pct}%`;
                if (label) label.textContent = `Uploading ${pct}%`;
            });

            // Notify backend upload is complete
            const completeResp = await API.completeGCSUpload(project_id, gcs_object_name);
            if (!completeResp.ok) {
                const err = await completeResp.json().catch(() => ({}));
                throw new Error(err.detail || 'Upload completion failed');
            }

            addLog('Upload complete: ' + selectedFile.name);
            Router.navigate('processing', { projectId: currentProjectId, start: true });
        } catch (error) {
            if (error.name === 'AbortError') {
                showToast('Upload timed out. Please try again.', 'error');
            } else {
                showToast(error.message, 'error');
            }
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload & Process';
            const progressEl = document.getElementById('uploadProgress');
            if (progressEl) progressEl.style.display = 'none';
        }
    },

    async _resumableUpload(uploadUrl, file, onProgress) {
        const CHUNK_SIZE = 8 * 1024 * 1024; // 8MB
        const totalSize = file.size;
        let offset = 0;

        while (offset < totalSize) {
            const end = Math.min(offset + CHUNK_SIZE, totalSize);
            const chunk = file.slice(offset, end);
            const isLast = end === totalSize;

            const contentRange = isLast
                ? `bytes ${offset}-${end - 1}/${totalSize}`
                : `bytes ${offset}-${end - 1}/*`;

            const resp = await fetch(uploadUrl, {
                method: 'PUT',
                headers: {
                    'Content-Range': contentRange,
                    'Content-Type': file.type || 'video/mp4',
                },
                body: chunk,
            });

            if (resp.status === 308) {
                // GCS Resume Incomplete — parse Range header for confirmed offset
                const range = resp.headers.get('Range');
                if (range) {
                    const match = range.match(/bytes=0-(\d+)/);
                    offset = match ? parseInt(match[1], 10) + 1 : end;
                } else {
                    offset = end;
                }
            } else if (resp.status === 200 || resp.status === 201) {
                offset = end;
            } else {
                const body = await resp.text();
                throw new Error(`GCS upload failed (HTTP ${resp.status}): ${body}`);
            }

            const pct = Math.round((offset / totalSize) * 100);
            onProgress(pct);
        }
    },

    async _legacyUpload() {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('name', selectedFile.name);
        formData.append('content_type', 'fps_montage');

        const response = await API.uploadFile(formData);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Upload failed');
        }
        const data = await response.json();
        currentProjectId = data.project_id;
        addLog('Upload complete: ' + selectedFile.name);
        Router.navigate('processing', { projectId: currentProjectId, start: true });
    },
};

// ══════════════════════════════════════════════════════════
// PROCESSING VIEW
// ══════════════════════════════════════════════════════════

const ProcessingView = {
    async init(opts = {}) {
        // Reset UI
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const statusMessage = document.getElementById('statusMessage');
        const logOutput = document.getElementById('logOutput');

        if (!opts.resume) {
            if (progressFill) progressFill.style.width = '0%';
            if (progressText) progressText.textContent = '0%';
            if (statusMessage) statusMessage.textContent = 'Preparing...';
            if (logOutput) logOutput.textContent = '';
            for (let i = 1; i <= 4; i++) {
                const step = document.getElementById(`step${i}`);
                if (step) step.classList.remove('active', 'completed');
            }
        }

        wsReconnectAttempts = 0;

        if (opts.projectId) currentProjectId = opts.projectId;

        if (opts.start) {
            await this.startProcessing();
        } else if (opts.resume) {
            // Re-attach WebSocket for an in-progress project
            connectWebSocket();
        }
    },

    async startProcessing() {
        try {
            addLog('Starting processing...');
            connectWebSocket();

            const response = await API.startProcessing(currentProjectId);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to start processing');
            }

            const data = await response.json();
            addLog('Processing started (task: ' + data.task_id + ')');
        } catch (error) {
            showError(error.message);
        }
    },
};

// ══════════════════════════════════════════════════════════
// RESULT VIEW
// ══════════════════════════════════════════════════════════

const ResultView = {
    async init(opts = {}) {
        if (opts.projectId) currentProjectId = opts.projectId;

        // Set up download button
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn) {
            downloadBtn.onclick = () => handleDownload();
        }

        try {
            const response = await API.getStatus(currentProjectId);
            const projectData = await response.json();
            const result = projectData.result || {};
            const qualityScore = result.quality_score || 0;
            const grade = getQualityGrade(qualityScore);
            const warnings = result.warnings || [];

            // Quality gauge
            const qualityGaugeEl = document.getElementById('qualityGauge');
            if (qualityGaugeEl) {
                qualityGaugeEl.innerHTML = `
                    <div class="quality-gauge">
                        <div class="quality-fill" style="width: ${Math.min(100, qualityScore)}%"></div>
                    </div>
                    <div class="quality-label">
                        <span class="quality-grade grade-${grade.toLowerCase()}">${grade}</span>
                        <span class="quality-value">${qualityScore.toFixed(1)}/100</span>
                    </div>
                `;
            }

            // Warnings
            const warningsEl = document.getElementById('warningsArea');
            if (warningsEl) {
                if (warnings.length > 0) {
                    warningsEl.style.display = 'block';
                    warningsEl.innerHTML = '<h4>Warnings</h4>' +
                        warnings.map(w => `<div class="warning-item">${escapeHtml(w)}</div>`).join('');
                } else {
                    warningsEl.style.display = 'none';
                }
            }

            // Stats
            let statsHtml = `
                <p><strong>Processing time:</strong> ${calculateProcessingTime(projectData)}</p>
                <p><strong>Clips detected:</strong> ${result.clip_count || 0}</p>
                <p><strong>Total duration:</strong> ${(result.total_duration || 0).toFixed(1)}s</p>
            `;

            const suggestions = result.suggestions || [];
            if (suggestions.length > 0) {
                statsHtml += '<div class="suggestions"><h4>Suggestions</h4><ul>' +
                    suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('') + '</ul></div>';
            }

            document.getElementById('resultStats').innerHTML = statsHtml;

            // Video preview
            const videoPreview = document.getElementById('videoPreview');
            if (videoPreview && result.output_path) {
                const videoUrl = `${BACKEND_URL}/api/download/${currentProjectId}`;
                videoPreview.innerHTML = `<video controls src="${videoUrl}"></video>`;
            }
        } catch (error) {
            console.error('Failed to load project stats:', error);
        }
    },
};

// ══════════════════════════════════════════════════════════
// WEBSOCKET (preserved with token auth)
// ══════════════════════════════════════════════════════════

function connectWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    let wsUrl;
    if (BACKEND_URL) {
        const backendWs = BACKEND_URL.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
        wsUrl = `${backendWs}/ws/${currentProjectId}`;
    } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/ws/${currentProjectId}`;
    }

    if (idToken) {
        wsUrl += `?token=${encodeURIComponent(idToken)}`;
    }

    websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
        wsReconnectAttempts = 0;
        updateConnectionStatus('connected');
        addLog('WebSocket connected');
    };

    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data && typeof data === 'object' && data.type) {
                handleProgressUpdate(data);
            }
        } catch (e) {
            console.warn('Invalid WebSocket message:', e);
        }
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
        updateConnectionStatus('disconnected');
        if (Router.currentView === 'processing') {
            attemptReconnect();
        }
    };
}

function attemptReconnect() {
    if (wsReconnectAttempts >= WS_MAX_RECONNECT) {
        addLog('WebSocket reconnection failed. Switching to polling...');
        updateConnectionStatus('polling');
        startPolling();
        return;
    }

    wsReconnectAttempts++;
    const backoff = WS_INITIAL_BACKOFF * Math.pow(2, wsReconnectAttempts - 1);
    addLog('Reconnecting WebSocket (' + wsReconnectAttempts + '/' + WS_MAX_RECONNECT + ')...');
    wsReconnectTimer = setTimeout(() => connectWebSocket(), backoff);
}

function startPolling() {
    if (pollingTimer) return;

    pollingTimer = setInterval(async () => {
        if (!currentProjectId) { stopPolling(); return; }
        try {
            const response = await API.getStatus(currentProjectId);
            if (!response.ok) return;

            const data = await response.json();
            if (data.status === 'completed') {
                handleProgressUpdate({
                    type: 'completion', progress: 100,
                    stage: 'completed', outputs: data.result,
                });
                stopPolling();
            } else if (data.status === 'failed') {
                handleProgressUpdate({
                    type: 'error', error: data.error || 'Processing failed',
                });
                stopPolling();
            } else if (data.progress) {
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                if (progressFill) progressFill.style.width = `${data.progress}%`;
                if (progressText) progressText.textContent = `${data.progress}%`;
            }
        } catch (e) {
            console.warn('Polling error:', e);
        }
    }, POLLING_INTERVAL);
}

function stopPolling() {
    if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
}

function updateConnectionStatus(status) {
    const indicator = document.getElementById('connectionStatus');
    if (!indicator) return;
    indicator.className = 'connection-status ' + status;
    const labels = { connected: 'Connected', disconnected: 'Disconnected', polling: 'Polling' };
    indicator.textContent = labels[status] || status;
}

// ══════════════════════════════════════════════════════════
// PROGRESS & RESULTS
// ══════════════════════════════════════════════════════════

function handleProgressUpdate(data) {
    const { type, stage, progress, message, outputs, error } = data;

    if (type === 'error') { showError(error || message || 'Processing failed'); return; }
    if (type === 'completion') { handleProcessingComplete(outputs); return; }

    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const statusMessage = document.getElementById('statusMessage');

    if (progress !== undefined) {
        if (progressFill) progressFill.style.width = `${progress}%`;
        if (progressText) progressText.textContent = `${progress}%`;
    }

    if (message || stage) {
        if (statusMessage) statusMessage.textContent = message || stage;
    }

    if (stage) {
        updateStepIndicators(stage);
        addLog('[' + stage + '] ' + (message || ''));
    }
}

function updateStepIndicators(stage) {
    const steps = {
        'extracting_frames': 'step1', 'frame_extraction': 'step1',
        'analyzing_frames': 'step2', 'ai_analysis': 'step2',
        'selecting_clips': 'step3', 'clip_detection': 'step3',
        'editing_video': 'step4', 'applying_effects': 'step4',
        'evaluating_quality': 'step4', 'finalizing': 'step4',
        'video_generation': 'step4', 'completed': 'step4',
    };

    const stepId = steps[stage];
    if (!stepId) return;

    const stepNumber = parseInt(stepId.replace('step', ''));
    for (let i = 1; i <= stepNumber; i++) {
        const step = document.getElementById(`step${i}`);
        if (!step) continue;
        if (stage === 'completed') {
            step.classList.add('completed');
            step.classList.remove('active');
        } else if (i === stepNumber) {
            step.classList.add('active');
            step.classList.remove('completed');
        } else {
            step.classList.add('completed');
            step.classList.remove('active');
        }
    }
}

function handleProcessingComplete(outputs) {
    addLog('Processing complete!');
    stopPolling();
    if (websocket) websocket.close();
    Router.navigate('result', { projectId: currentProjectId });
}

async function handleCancelProcessing() {
    if (!currentProjectId) return;
    try {
        const response = await API.cancelProject(currentProjectId);
        if (response.ok) {
            addLog('Processing cancelled by user');
            showToast('Processing cancelled');
            Router.navigate('dashboard');
        }
    } catch (error) {
        console.error('Cancel failed:', error);
    }
}

function calculateProcessingTime(jobData) {
    const start = new Date(jobData.created_at);
    const end = new Date();
    const diff = Math.floor((end - start) / 1000);
    return `${Math.floor(diff / 60)}m ${diff % 60}s`;
}

function getQualityGrade(score) {
    if (score >= 90) return 'A';
    if (score >= 75) return 'B';
    if (score >= 60) return 'C';
    if (score >= 40) return 'D';
    if (score >= 20) return 'E';
    return 'F';
}

// ══════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════

function showError(message) {
    Router.navigate('error');
    document.getElementById('errorMessage').textContent = message;
    stopPolling();
    if (websocket) websocket.close();
    addLog('Error: ' + message);
}

function handleDownload() {
    if (currentProjectId) {
        window.location.href = `${BACKEND_URL}/api/download/${currentProjectId}`;
        addLog('Download started');
    }
}

function addLog(message) {
    const logOutput = document.getElementById('logOutput');
    if (!logOutput) return;
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
    logOutput.textContent += `[${timestamp}] ${message}\n`;
    logOutput.scrollTop = logOutput.scrollHeight;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ══════════════════════════════════════════════════════════
// EVENT LISTENERS
// ══════════════════════════════════════════════════════════

function setupEventListeners() {
    // Landing page CTAs → open auth modal
    const landingSignIn = document.getElementById('landingSignInBtn');
    const heroCTA = document.getElementById('heroCTABtn');
    const ctaBottom = document.getElementById('ctaBottomBtn');
    if (landingSignIn) landingSignIn.addEventListener('click', openAuthModal);
    if (heroCTA) heroCTA.addEventListener('click', openAuthModal);
    if (ctaBottom) ctaBottom.addEventListener('click', openAuthModal);

    // Auth modal
    const authBackdrop = document.getElementById('authModalBackdrop');
    const authClose = document.getElementById('authModalClose');
    const authToggle = document.getElementById('authToggleBtn');
    if (authBackdrop) authBackdrop.addEventListener('click', closeAuthModal);
    if (authClose) authClose.addEventListener('click', closeAuthModal);
    if (authToggle) authToggle.addEventListener('click', toggleAuthMode);

    const googleBtn = document.getElementById('googleSignInBtn');
    if (googleBtn) googleBtn.addEventListener('click', signInWithGoogle);

    const emailForm = document.getElementById('emailAuthForm');
    if (emailForm) emailForm.addEventListener('submit', (e) => { e.preventDefault(); handleEmailSubmit(); });

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', signOut);

    // Settings modal
    const settingsNav = document.getElementById('settingsNavBtn');
    if (settingsNav) settingsNav.addEventListener('click', (e) => { e.preventDefault(); openSettingsModal(); });
    const settingsClose = document.getElementById('settingsModalClose');
    const settingsBackdrop = document.getElementById('settingsModalBackdrop');
    if (settingsClose) settingsClose.addEventListener('click', closeSettingsModal);
    if (settingsBackdrop) settingsBackdrop.addEventListener('click', closeSettingsModal);
    const settingsSave = document.getElementById('settingsSaveBtn');
    const settingsClear = document.getElementById('settingsClearBtn');
    if (settingsSave) settingsSave.addEventListener('click', saveSettings);
    if (settingsClear) settingsClear.addEventListener('click', clearSettings);

    // Sidebar navigation
    document.querySelectorAll('.nav-item[data-view]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            Router.navigate(item.dataset.view);
        });
    });

    // Dashboard new-project buttons
    const dashNew = document.getElementById('dashNewProjectBtn');
    const emptyNew = document.getElementById('emptyNewProjectBtn');
    if (dashNew) dashNew.addEventListener('click', () => Router.navigate('upload'));
    if (emptyNew) emptyNew.addEventListener('click', () => Router.navigate('upload'));

    // Upload area
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadArea');

    if (fileInput) fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) UploadView.setFile(file);
    });

    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) UploadView.setFile(file);
        });
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    if (uploadBtn) uploadBtn.addEventListener('click', () => UploadView.upload());
    if (cancelBtn) cancelBtn.addEventListener('click', () => UploadView.cancelFile());

    // Processing
    const cancelProcessBtn = document.getElementById('cancelProcessBtn');
    if (cancelProcessBtn) cancelProcessBtn.addEventListener('click', handleCancelProcessing);

    // Result
    const downloadBtn = document.getElementById('downloadBtn');
    const newUploadBtn = document.getElementById('newUploadBtn');
    const backToDash = document.getElementById('backToDashBtn');
    if (downloadBtn) downloadBtn.addEventListener('click', handleDownload);
    if (newUploadBtn) newUploadBtn.addEventListener('click', () => Router.navigate('upload'));
    if (backToDash) backToDash.addEventListener('click', () => Router.navigate('dashboard'));

    // Error
    const retryBtn = document.getElementById('retryBtn');
    const errorBack = document.getElementById('errorBackBtn');
    if (retryBtn) retryBtn.addEventListener('click', () => Router.navigate('upload'));
    if (errorBack) errorBack.addEventListener('click', () => Router.navigate('dashboard'));

    // Mobile sidebar
    const hamburger = document.getElementById('hamburgerBtn');
    const sidebarClose = document.getElementById('sidebarClose');
    if (hamburger) hamburger.addEventListener('click', openMobileSidebar);
    if (sidebarClose) sidebarClose.addEventListener('click', closeMobileSidebar);

    // Create sidebar overlay for mobile
    const overlay = document.createElement('div');
    overlay.id = 'sidebarOverlay';
    overlay.className = 'sidebar-overlay';
    overlay.addEventListener('click', closeMobileSidebar);
    document.body.appendChild(overlay);
}

// ══════════════════════════════════════════════════════════
// INITIALIZATION
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();

    // Show loading while Firebase initializes
    showLoading();
    await initFirebase();
});

// Prevent page unload during processing
window.addEventListener('beforeunload', (e) => {
    if (Router.currentView === 'processing') {
        e.preventDefault();
        e.returnValue = 'Processing in progress. Leave page?';
    }
});
