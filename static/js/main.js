// ClipMontage Frontend JavaScript
// v2.2 — Firebase Authentication + Bearer tokens

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

const WS_MAX_RECONNECT = 5;
const WS_INITIAL_BACKOFF = 1000;
const POLLING_INTERVAL = 5000;
const FETCH_TIMEOUT = 30000;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const selectedFileDiv = document.getElementById('selectedFile');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const uploadBtn = document.getElementById('uploadBtn');
const cancelBtn = document.getElementById('cancelBtn');

const authSection = document.getElementById('authSection');
const uploadSection = document.getElementById('uploadSection');
const processingSection = document.getElementById('processingSection');
const resultSection = document.getElementById('resultSection');
const errorSection = document.getElementById('errorSection');

const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusMessage = document.getElementById('statusMessage');
const logOutput = document.getElementById('logOutput');

const downloadBtn = document.getElementById('downloadBtn');
const newUploadBtn = document.getElementById('newUploadBtn');
const retryBtn = document.getElementById('retryBtn');

// ══════════════════════════════════════════════════════════
// INITIALIZATION
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await initFirebase();
});

function hideLoading() {
    const el = document.getElementById('loadingIndicator');
    if (el) el.style.display = 'none';
}

async function initFirebase() {
    try {
        const resp = await fetch('/api/config/firebase');
        const config = await resp.json();

        if (!config.enabled) {
            firebaseEnabled = false;
            hideLoading();
            showUploadSection();
            // Firebase auth disabled — dev mode
            return;
        }

        firebaseEnabled = true;

        // Dynamically load Firebase SDK
        await loadScript('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
        await loadScript('https://www.gstatic.com/firebasejs/10.12.0/firebase-auth-compat.js');

        firebaseApp = firebase.initializeApp({
            apiKey: config.apiKey,
            authDomain: config.authDomain,
            projectId: config.projectId,
        });
        firebaseAuth = firebase.auth();

        // Listen for auth state changes
        firebaseAuth.onAuthStateChanged(async (user) => {
            // Clear any existing token refresh timer
            if (tokenRefreshTimer) {
                clearInterval(tokenRefreshTimer);
                tokenRefreshTimer = null;
            }

            hideLoading();

            if (user) {
                currentUser = user;
                idToken = await user.getIdToken();
                showLoggedIn(user);
                showUploadSection();

                // Refresh token periodically (every 50 minutes)
                tokenRefreshTimer = setInterval(async () => {
                    if (currentUser) {
                        try {
                            idToken = await currentUser.getIdToken(true);
                            // token refreshed
                        } catch (e) {
                            console.warn('Token refresh failed:', e);
                        }
                    }
                }, 50 * 60 * 1000);
            } else {
                currentUser = null;
                idToken = null;
                showAuthSection();
            }
        });
    } catch (e) {
        console.error('Firebase init failed:', e);
        firebaseEnabled = false;
        hideLoading();
        showUploadSection();
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

// ══════════════════════════════════════════════════════════
// AUTH UI
// ══════════════════════════════════════════════════════════

function showAuthSection() {
    authSection.style.display = 'block';
    uploadSection.style.display = 'none';
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    errorSection.style.display = 'none';
    document.getElementById('userBar').style.display = 'none';
}

function showUploadSection() {
    if (authSection) authSection.style.display = 'none';
    uploadSection.style.display = 'block';
}

function showLoggedIn(user) {
    const userBar = document.getElementById('userBar');
    const userAvatar = document.getElementById('userAvatar');
    const userNameEl = document.getElementById('userName');

    if (userBar) userBar.style.display = 'flex';
    if (userNameEl) userNameEl.textContent = user.displayName || user.email || 'User';
    if (userAvatar) {
        if (user.photoURL) {
            userAvatar.src = user.photoURL;
            userAvatar.style.display = 'block';
        } else {
            userAvatar.style.display = 'none';
        }
    }
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
// AUTH ACTIONS
// ══════════════════════════════════════════════════════════

async function signInWithGoogle() {
    clearAuthError();
    try {
        const provider = new firebase.auth.GoogleAuthProvider();
        await firebaseAuth.signInWithPopup(provider);
    } catch (e) {
        showAuthError(e.message);
    }
}

async function signInWithEmail() {
    clearAuthError();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;
    try {
        await firebaseAuth.signInWithEmailAndPassword(email, password);
    } catch (e) {
        showAuthError(e.message);
    }
}

async function signUpWithEmail() {
    clearAuthError();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;
    try {
        await firebaseAuth.createUserWithEmailAndPassword(email, password);
    } catch (e) {
        showAuthError(e.message);
    }
}

async function signOut() {
    // Clean up processing state
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
    // onAuthStateChanged will fire and call showAuthSection()
}

// ══════════════════════════════════════════════════════════
// AUTHENTICATED FETCH
// ══════════════════════════════════════════════════════════

function getAuthHeaders() {
    const headers = {};
    if (idToken) {
        headers['Authorization'] = `Bearer ${idToken}`;
    }
    return headers;
}

function fetchWithTimeout(url, options = {}, timeout = FETCH_TIMEOUT) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    // Merge auth headers
    const authHeaders = getAuthHeaders();
    const mergedHeaders = { ...(options.headers || {}), ...authHeaders };

    return fetch(url, {
        ...options,
        headers: mergedHeaders,
        signal: controller.signal,
    }).finally(() => clearTimeout(timer));
}

// ══════════════════════════════════════════════════════════
// EVENT LISTENERS
// ══════════════════════════════════════════════════════════

function setupEventListeners() {
    if (fileInput) fileInput.addEventListener('change', handleFileSelect);

    if (uploadArea) {
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('dragleave', handleDragLeave);
        uploadArea.addEventListener('drop', handleDrop);
    }

    if (uploadBtn) uploadBtn.addEventListener('click', handleUpload);
    if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);
    if (downloadBtn) downloadBtn.addEventListener('click', handleDownload);
    if (newUploadBtn) newUploadBtn.addEventListener('click', resetToUpload);
    if (retryBtn) retryBtn.addEventListener('click', resetToUpload);

    const cancelProcessBtn = document.getElementById('cancelProcessBtn');
    if (cancelProcessBtn) cancelProcessBtn.addEventListener('click', handleCancelProcessing);

    // Auth buttons
    const googleBtn = document.getElementById('googleSignInBtn');
    if (googleBtn) googleBtn.addEventListener('click', signInWithGoogle);

    const emailForm = document.getElementById('emailAuthForm');
    if (emailForm) emailForm.addEventListener('submit', (e) => { e.preventDefault(); signInWithEmail(); });

    const signUpBtn = document.getElementById('emailSignUpBtn');
    if (signUpBtn) signUpBtn.addEventListener('click', signUpWithEmail);

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', signOut);

    // Event listeners initialized
}

// ══════════════════════════════════════════════════════════
// FILE HANDLING
// ══════════════════════════════════════════════════════════

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) setSelectedFile(file);
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
}

function setSelectedFile(file) {
    selectedFile = file;
    const validExtensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!validExtensions.includes(fileExt)) {
        showError('Invalid file format. Supported: MP4, MKV, AVI, MOV, WebM');
        return;
    }

    const maxSize = 20 * 1024 * 1024 * 1024;
    if (file.size > maxSize) {
        showError('File too large. Maximum size: 20GB');
        return;
    }

    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    uploadArea.style.display = 'none';
    selectedFileDiv.style.display = 'block';
}

function handleCancel() {
    selectedFile = null;
    fileInput.value = '';
    uploadArea.style.display = 'block';
    selectedFileDiv.style.display = 'none';
}

// ══════════════════════════════════════════════════════════
// UPLOAD & PROCESSING
// ══════════════════════════════════════════════════════════

async function handleUpload() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('name', selectedFile.name);
    formData.append('content_type', 'fps_montage');

    try {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading...';

        const response = await fetchWithTimeout('/api/processing/upload', {
            method: 'POST',
            body: formData,
        }, 120000);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Upload failed');
        }

        const data = await response.json();
        currentProjectId = data.project_id;
        addLog('Upload complete: ' + selectedFile.name);
        await startProcessing();

    } catch (error) {
        if (error.name === 'AbortError') {
            showUploadError('Upload timed out. Please try again.');
        } else {
            showUploadError(error.message);
        }
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
    }
}

function showUploadError(message) {
    uploadSection.style.display = 'none';
    errorSection.style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
    addLog('Error: ' + message);
}

async function startProcessing() {
    try {
        uploadSection.style.display = 'none';
        processingSection.style.display = 'block';
        addLog('Starting processing...');

        connectWebSocket();

        const response = await fetchWithTimeout('/api/processing/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: currentProjectId,
                content_type: 'fps_montage',
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to start processing');
        }

        const data = await response.json();
        addLog('Processing started (task: ' + data.task_id + ')');
    } catch (error) {
        showError(error.message);
    }
}

// ══════════════════════════════════════════════════════════
// WEBSOCKET (with token auth)
// ══════════════════════════════════════════════════════════

function connectWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsUrl = `${protocol}//${window.location.host}/ws/${currentProjectId}`;

    // Pass token as query param for WebSocket auth
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
        if (processingSection.style.display === 'block') {
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
            const response = await fetchWithTimeout(`/api/processing/status/${currentProjectId}`);
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
                progressFill.style.width = `${data.progress}%`;
                progressText.textContent = `${data.progress}%`;
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

    if (progress !== undefined) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
    }

    if (message || stage) statusMessage.textContent = message || stage;

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

async function handleProcessingComplete(outputs) {
    addLog('Processing complete!');
    stopPolling();
    if (websocket) websocket.close();

    processingSection.style.display = 'none';
    resultSection.style.display = 'block';

    downloadBtn.onclick = () => {
        window.location.href = `/api/download/${currentProjectId}`;
    };

    try {
        const response = await fetchWithTimeout(`/api/processing/status/${currentProjectId}`);
        const projectData = await response.json();
        const result = projectData.result || {};
        const qualityScore = result.quality_score || 0;
        const grade = getQualityGrade(qualityScore);
        const warnings = result.warnings || [];

        let statsHtml = `
            <p><strong>Processing time:</strong> ${calculateProcessingTime(projectData)}</p>
            <p><strong>Clips detected:</strong> ${result.clip_count || 0}</p>
            <p><strong>Total duration:</strong> ${(result.total_duration || 0).toFixed(1)}s</p>
        `;

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

        const warningsEl = document.getElementById('warningsArea');
        if (warningsEl && warnings.length > 0) {
            warningsEl.style.display = 'block';
            warningsEl.innerHTML = '<h4>Warnings</h4>' +
                warnings.map(w => `<div class="warning-item">${w}</div>`).join('');
        }

        const suggestions = result.suggestions || [];
        if (suggestions.length > 0) {
            statsHtml += '<div class="suggestions"><h4>Suggestions</h4><ul>' +
                suggestions.map(s => `<li>${s}</li>`).join('') + '</ul></div>';
        }

        document.getElementById('resultStats').innerHTML = statsHtml;
    } catch (error) {
        console.error('Failed to load project stats:', error);
    }
}

function getQualityGrade(score) {
    if (score >= 90) return 'A';
    if (score >= 75) return 'B';
    if (score >= 60) return 'C';
    if (score >= 40) return 'D';
    if (score >= 20) return 'E';
    return 'F';
}

async function handleCancelProcessing() {
    if (!currentProjectId) return;
    try {
        const response = await fetchWithTimeout(`/api/projects/${currentProjectId}/cancel`, {
            method: 'POST',
        });
        if (response.ok) {
            addLog('Processing cancelled by user');
            showError('Processing cancelled');
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

// ══════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════

function showError(message) {
    uploadSection.style.display = 'none';
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    errorSection.style.display = 'block';
    if (authSection) authSection.style.display = 'none';

    document.getElementById('errorMessage').textContent = message;
    stopPolling();
    if (websocket) websocket.close();
    addLog('Error: ' + message);
}

function resetToUpload() {
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    errorSection.style.display = 'none';

    // If Firebase is enabled but user is logged out, show auth instead
    if (firebaseEnabled && !currentUser) {
        showAuthSection();
    } else {
        if (authSection) authSection.style.display = 'none';
        uploadSection.style.display = 'block';
    }

    currentProjectId = null;
    selectedFile = null;
    fileInput.value = '';
    wsReconnectAttempts = 0;

    uploadArea.style.display = 'block';
    selectedFileDiv.style.display = 'none';

    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    statusMessage.textContent = 'Preparing...';
    logOutput.textContent = '';

    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step${i}`);
        if (step) step.classList.remove('active', 'completed');
    }

    const warningsEl = document.getElementById('warningsArea');
    if (warningsEl) warningsEl.style.display = 'none';
    const qualityEl = document.getElementById('qualityGauge');
    if (qualityEl) qualityEl.innerHTML = '';

    stopPolling();
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
}

function handleDownload() {
    if (currentProjectId) {
        window.location.href = `/api/download/${currentProjectId}`;
        addLog('Download started');
    }
}

function addLog(message) {
    const timestamp = new Date().toLocaleTimeString('ja-JP');
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

// Prevent page unload during processing
window.addEventListener('beforeunload', (e) => {
    if (processingSection.style.display === 'block') {
        e.preventDefault();
        e.returnValue = 'Processing in progress. Leave page?';
    }
});
