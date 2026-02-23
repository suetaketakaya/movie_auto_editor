// ClipMontage Frontend — v4.0
// SPA with Router, View Controllers
// Firebase Auth + Browser-side Processing Pipeline

// ══════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════

let selectedFile = null;

// Firebase state
let firebaseApp = null;
let firebaseAuth = null;
let currentUser = null;
let idToken = null;
let firebaseEnabled = false;
let tokenRefreshTimer = null;

// Auth modal state
let authIsSignUp = false;

// Local processing state
let activePipeline = null;
let lastResultBlob = null;
let lastResultStats = null;
let processingStartTime = null;

const BACKEND_URL = window.location.hostname === 'localhost'
    ? ''
    : 'https://movie-auto-editor-1.onrender.com';

// ══════════════════════════════════════════════════════════
// (API client removed — all processing is now browser-side)
// ══════════════════════════════════════════════════════════

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
    if (activePipeline) {
        activePipeline.cancel();
        activePipeline = null;
    }
    lastResultBlob = null;
    lastResultStats = null;

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
    const input = document.getElementById('settingsHfToken');
    const saved = localStorage.getItem('hf_api_key');
    if (input && saved) input.value = saved;
}

function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'none';
}

function saveSettings() {
    const input = document.getElementById('settingsHfToken');
    const status = document.getElementById('settingsStatus');
    const key = input ? input.value.trim() : '';
    if (key) {
        localStorage.setItem('hf_api_key', key);
        if (status) {
            status.style.display = 'block';
            status.style.color = '#4ade80';
            status.textContent = 'API token saved. It will be used for video analysis.';
        }
    } else {
        if (status) {
            status.style.display = 'block';
            status.style.color = '#f87171';
            status.textContent = 'Please enter a valid API token.';
        }
    }
}

function clearSettings() {
    localStorage.removeItem('hf_api_key');
    const input = document.getElementById('settingsHfToken');
    const status = document.getElementById('settingsStatus');
    if (input) input.value = '';
    if (status) {
        status.style.display = 'block';
        status.style.color = '#facc15';
        status.textContent = 'API token cleared. You will need to set one before processing.';
    }
}

// ══════════════════════════════════════════════════════════
// DASHBOARD VIEW
// ══════════════════════════════════════════════════════════

const DashboardView = {
    async init() {
        // Local-only mode: show stats from last session if available
        document.getElementById('statTotal').textContent = lastResultBlob ? '1' : '0';
        document.getElementById('statCompleted').textContent = lastResultBlob ? '1' : '0';
        document.getElementById('statProcessing').textContent = activePipeline ? '1' : '0';
        document.getElementById('statFailed').textContent = '0';

        const grid = document.getElementById('projectGrid');
        const empty = document.getElementById('emptyState');

        if (lastResultBlob) {
            empty.style.display = 'none';
            grid.style.display = 'grid';
            const stats = lastResultStats || {};
            grid.innerHTML = `
                <div class="project-card" data-status="completed" style="cursor:pointer;">
                    <div class="project-card-header">
                        <span class="project-card-name">Last Result</span>
                        <span class="project-status status-completed">completed</span>
                    </div>
                    <div class="project-card-meta">
                        <span class="project-card-date">${stats.clipCount || 0} clips, ${(stats.totalDuration || 0).toFixed(1)}s</span>
                    </div>
                </div>
            `;
            grid.querySelector('.project-card').addEventListener('click', () => {
                Router.navigate('result', { fromLocal: true });
            });
        } else {
            grid.innerHTML = '';
            grid.style.display = 'none';
            empty.style.display = 'block';
        }
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

        // Check for API key before starting
        const apiKey = localStorage.getItem('hf_api_key');
        if (!apiKey) {
            showToast('Please set your HuggingFace API token in Settings first.', 'error');
            openSettingsModal();
            return;
        }

        const uploadBtn = document.getElementById('uploadBtn');
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Starting...';

        try {
            // Navigate to processing view and start the local pipeline
            Router.navigate('processing', { start: true, file: selectedFile });
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload & Process';
        }
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

        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = '0%';
        if (statusMessage) statusMessage.textContent = 'Preparing...';
        if (logOutput) logOutput.textContent = '';
        for (let i = 1; i <= 4; i++) {
            const step = document.getElementById(`step${i}`);
            if (step) step.classList.remove('active', 'completed');
        }

        // Show "Local Processing" status
        updateConnectionStatus('local');

        if (opts.start && opts.file) {
            await this.startLocalProcessing(opts.file);
        }
    },

    async startLocalProcessing(file) {
        const apiKey = localStorage.getItem('hf_api_key');
        if (!apiKey) {
            showError('HuggingFace API token not set. Please configure it in Settings.');
            return;
        }

        processingStartTime = Date.now();

        activePipeline = new ProcessingPipeline({
            apiKey,
            onProgress: (data) => handleProgressUpdate(data),
            onLog: (msg) => addLog(msg),
            onComplete: (blob, stats) => {
                lastResultBlob = blob;
                lastResultStats = stats;
                activePipeline = null;
                handleProcessingComplete();
            },
            onError: (msg) => {
                activePipeline = null;
                showError(msg);
            },
        });

        activePipeline.run(file);
    },
};

// ══════════════════════════════════════════════════════════
// RESULT VIEW
// ══════════════════════════════════════════════════════════

const ResultView = {
    _blobUrl: null,

    async init(opts = {}) {
        // Clean up previous blob URL
        if (this._blobUrl) {
            URL.revokeObjectURL(this._blobUrl);
            this._blobUrl = null;
        }

        if (!lastResultBlob || !lastResultStats) {
            document.getElementById('resultStats').innerHTML = '<p>No result available.</p>';
            return;
        }

        const stats = lastResultStats;
        const qualityScore = stats.qualityScore || 0;
        const grade = getQualityGrade(qualityScore);
        const warnings = stats.warnings || [];

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
        const procTime = stats.processingTime || '0';
        let statsHtml = `
            <p><strong>Processing time:</strong> ${procTime}s</p>
            <p><strong>Clips detected:</strong> ${stats.clipCount || 0}</p>
            <p><strong>Total duration:</strong> ${(stats.totalDuration || 0).toFixed(1)}s</p>
            <p><strong>Output size:</strong> ${formatFileSize(stats.outputSize || 0)}</p>
        `;

        const suggestions = stats.suggestions || [];
        if (suggestions.length > 0) {
            statsHtml += '<div class="suggestions"><h4>Suggestions</h4><ul>' +
                suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('') + '</ul></div>';
        }

        document.getElementById('resultStats').innerHTML = statsHtml;

        // Video preview from Blob URL
        const videoPreview = document.getElementById('videoPreview');
        if (videoPreview && lastResultBlob) {
            this._blobUrl = URL.createObjectURL(lastResultBlob);
            videoPreview.innerHTML = `<video controls src="${this._blobUrl}"></video>`;
        }
    },
};

// ══════════════════════════════════════════════════════════
// CONNECTION STATUS (local processing indicator)
// ══════════════════════════════════════════════════════════

function updateConnectionStatus(status) {
    const indicator = document.getElementById('connectionStatus');
    if (!indicator) return;
    indicator.className = 'connection-status ' + status;
    const labels = { local: 'Local Processing', connected: 'Connected', disconnected: 'Disconnected' };
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

function handleProcessingComplete() {
    addLog('Processing complete!');
    Router.navigate('result', { fromLocal: true });
}

async function handleCancelProcessing() {
    if (activePipeline) {
        activePipeline.cancel();
        activePipeline = null;
        addLog('Processing cancelled by user');
        showToast('Processing cancelled');
        Router.navigate('dashboard');
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

// ══════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════

function showError(message) {
    Router.navigate('error');
    document.getElementById('errorMessage').textContent = message;
    addLog('Error: ' + message);
}

function handleDownload() {
    if (!lastResultBlob) {
        showToast('No result available to download.', 'error');
        return;
    }
    const url = URL.createObjectURL(lastResultBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'highlight_reel.mp4';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    addLog('Download started');
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
