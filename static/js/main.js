// Auto-FPS-Clipper Frontend JavaScript
// Updated for Backend v4 API

let currentProjectId = null;
let websocket = null;
let selectedFile = null;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const selectedFileDiv = document.getElementById('selectedFile');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const uploadBtn = document.getElementById('uploadBtn');
const cancelBtn = document.getElementById('cancelBtn');

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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    // File input
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    // Drag and drop (uploadAreaのclick削除 - labelのfor属性を使用)
    if (uploadArea) {
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('dragleave', handleDragLeave);
        uploadArea.addEventListener('drop', handleDrop);
    }

    // Buttons
    if (uploadBtn) uploadBtn.addEventListener('click', handleUpload);
    if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);
    if (downloadBtn) downloadBtn.addEventListener('click', handleDownload);
    if (newUploadBtn) newUploadBtn.addEventListener('click', resetToUpload);
    if (retryBtn) retryBtn.addEventListener('click', resetToUpload);

    console.log('Event listeners initialized successfully');
}

function handleFileSelect(e) {
    console.log('File input change event triggered');
    const file = e.target.files[0];
    if (file) {
        console.log('File selected:', file.name, file.size, 'bytes');
        setSelectedFile(file);
    } else {
        console.log('No file selected');
    }
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
    if (file) {
        setSelectedFile(file);
    }
}

function setSelectedFile(file) {
    selectedFile = file;

    // Validate file type
    const validExtensions = ['.mp4', '.mkv', '.avi', '.mov'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!validExtensions.includes(fileExt)) {
        showError('無効なファイル形式です。MP4, MKV, AVI, MOVファイルのみ対応しています。');
        return;
    }

    // Validate file size (20GB max)
    const maxSize = 20 * 1024 * 1024 * 1024; // 20GB
    if (file.size > maxSize) {
        showError('ファイルサイズが大きすぎます。最大20GBまで対応しています。');
        return;
    }

    // Update UI
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

async function handleUpload() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('name', selectedFile.name);
    formData.append('content_type', 'fps_montage');

    try {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'アップロード中...';

        const response = await fetch('/api/processing/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'アップロードに失敗しました');
        }

        const data = await response.json();
        currentProjectId = data.project_id;

        addLog(`✅ ファイルアップロード完了: ${selectedFile.name}`);

        // Start processing
        await startProcessing();

    } catch (error) {
        showError(error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'アップロード開始';
    }
}

async function startProcessing() {
    try {
        // Show processing section
        uploadSection.style.display = 'none';
        processingSection.style.display = 'block';

        addLog('🚀 処理を開始します...');

        // Connect WebSocket
        connectWebSocket();

        // Start processing via v4 API
        const response = await fetch('/api/processing/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                project_id: currentProjectId,
                content_type: 'fps_montage'
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '処理の開始に失敗しました');
        }

        const data = await response.json();
        addLog(`⚙️ 処理が開始されました (タスク: ${data.task_id})`);

    } catch (error) {
        showError(error.message);
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${currentProjectId}`;

    websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
        addLog('🔌 WebSocket接続確立');
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('⚠️ リアルタイム更新の接続に失敗しました');
    };

    websocket.onclose = () => {
        addLog('🔌 WebSocket接続終了');
    };
}

function handleProgressUpdate(data) {
    const { stage, progress, message, output_file } = data;

    // Update progress bar
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;

    // Update status message
    statusMessage.textContent = message;

    // Update step indicators
    updateStepIndicators(stage);

    // Add log
    addLog(`[${stage}] ${message}`);

    // Check if completed
    if (stage === 'completed') {
        handleProcessingComplete(output_file);
    } else if (stage === 'failed') {
        showError(message);
    }
}

function updateStepIndicators(stage) {
    const steps = {
        'frame_extraction': 'step1',
        'ai_analysis': 'step2',
        'clip_detection': 'step3',
        'video_generation': 'step4',
        'completed': 'step4'
    };

    const stepId = steps[stage];
    if (!stepId) return;

    // Mark all previous steps as completed
    const stepNumber = parseInt(stepId.replace('step', ''));
    for (let i = 1; i <= stepNumber; i++) {
        const step = document.getElementById(`step${i}`);
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

async function handleProcessingComplete(outputFile) {
    addLog('🎉 処理が完了しました！');

    if (websocket) {
        websocket.close();
    }

    // Show result section
    processingSection.style.display = 'none';
    resultSection.style.display = 'block';

    // Setup download button
    downloadBtn.onclick = () => {
        window.location.href = outputFile || `/api/download/${currentProjectId}`;
    };

    // Load project stats from v4 API
    try {
        const response = await fetch(`/api/processing/status/${currentProjectId}`);
        const projectData = await response.json();

        const result = projectData.result || {};
        const stats = `
            <p><strong>処理時間:</strong> ${calculateProcessingTime(projectData)}</p>
            <p><strong>検出されたクリップ数:</strong> ${result.clip_count || 0}</p>
            <p><strong>品質スコア:</strong> ${result.quality_score ? result.quality_score.toFixed(1) : 'N/A'}</p>
        `;

        document.getElementById('resultStats').innerHTML = stats;
    } catch (error) {
        console.error('Failed to load project stats:', error);
    }
}

function calculateProcessingTime(jobData) {
    // Calculate time difference
    const start = new Date(jobData.created_at);
    const end = new Date();
    const diff = Math.floor((end - start) / 1000); // seconds

    const minutes = Math.floor(diff / 60);
    const seconds = diff % 60;

    return `${minutes}分${seconds}秒`;
}

function showError(message) {
    uploadSection.style.display = 'none';
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    errorSection.style.display = 'block';

    document.getElementById('errorMessage').textContent = message;

    if (websocket) {
        websocket.close();
    }

    addLog(`❌ エラー: ${message}`);
}

function resetToUpload() {
    // Reset all sections
    uploadSection.style.display = 'block';
    processingSection.style.display = 'none';
    resultSection.style.display = 'none';
    errorSection.style.display = 'none';

    // Reset state
    currentProjectId = null;
    selectedFile = null;
    fileInput.value = '';

    uploadArea.style.display = 'block';
    selectedFileDiv.style.display = 'none';

    // Reset progress
    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    statusMessage.textContent = '準備中...';
    logOutput.textContent = '';

    // Reset steps
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step${i}`);
        step.classList.remove('active', 'completed');
    }
}

function handleDownload() {
    if (currentProjectId) {
        window.location.href = `/api/download/${currentProjectId}`;
        addLog('📥 ダウンロードを開始しました');
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
        e.returnValue = '処理中です。ページを離れますか？';
    }
});
