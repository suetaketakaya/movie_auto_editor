# ClipMontage - Local Development Server
# Usage: .\start_local.ps1

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "ClipMontage Local Server"

Write-Host ""
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host "    ClipMontage - Local Environment" -ForegroundColor White
Write-Host "    AI Video Montage Generation" -ForegroundColor Gray
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# ── Environment Variables ────────────────────────
$env:APP_ENV = "development"
$env:PERSISTENCE_BACKEND = "memory"
$env:FIREBASE_ENABLED = "true"
$env:FIREBASE_PROJECT_ID = "moviecutter"
$env:FIREBASE_AUTH_DOMAIN = "moviecutter.firebaseapp.com"
$env:FIREBASE_API_KEY = "AIzaSyA1w0t5mlM8bH0RHd1Dp6Ziins32_thAM0"
$env:GCS_ENABLED = "false"
$env:ALLOWED_ORIGIN = "*"

# ── Firebase SA Key ──────────────────────────────
$saFile = Get-ChildItem -Path "." -Filter "moviecutter-firebase-adminsdk-*.json" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($saFile) {
    $env:FIREBASE_CREDENTIALS_PATH = $saFile.FullName
    Write-Host "  [OK] Firebase SA: $($saFile.Name)" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Firebase SA key not found" -ForegroundColor Yellow
    Write-Host "         Place moviecutter-firebase-adminsdk-*.json in project root" -ForegroundColor Gray
}

# ── Virtual Environment ──────────────────────────
$venvPath = $null
if (Test-Path ".venv\Scripts\Activate.ps1") { $venvPath = ".venv" }
elseif (Test-Path "venv\Scripts\Activate.ps1") { $venvPath = "venv" }

if ($venvPath) {
    & "$venvPath\Scripts\Activate.ps1"
    Write-Host "  [OK] Virtual env: $venvPath" -ForegroundColor Green
} else {
    Write-Host "  [SETUP] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & ".venv\Scripts\Activate.ps1"
    pip install --upgrade pip | Out-Null
    pip install -r requirements.txt
    Write-Host "  [OK] Dependencies installed" -ForegroundColor Green
}

# ── System Checks ────────────────────────────────
Write-Host ""
Write-Host "  -- System Check --" -ForegroundColor Cyan

# Python
$pyVer = python --version 2>&1
Write-Host "  [OK] $pyVer" -ForegroundColor Green

# FFmpeg
$ffmpegOk = $false
try {
    ffmpeg -version 2>&1 | Out-Null
    $ffmpegOk = $true
    Write-Host "  [OK] FFmpeg installed" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] FFmpeg not found!" -ForegroundColor Red
    Write-Host "         Install from https://ffmpeg.org/download.html" -ForegroundColor Gray
}

# Ollama
Write-Host ""
Write-Host "  -- Ollama AI Server --" -ForegroundColor Cyan

$ollamaOk = $false
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    $ollamaOk = $true
    Write-Host "  [OK] Ollama running" -ForegroundColor Green
    foreach ($model in $resp.models) {
        $size = [math]::Round($model.size / 1GB, 1)
        Write-Host "       - $($model.name) (${size}GB)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  [WARN] Ollama not running. Attempting to start..." -ForegroundColor Yellow
    try {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized -ErrorAction Stop
        Start-Sleep -Seconds 3
        $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $ollamaOk = $true
        Write-Host "  [OK] Ollama started" -ForegroundColor Green
        foreach ($model in $resp.models) {
            Write-Host "       - $($model.name)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  [WARN] Could not start Ollama. Install from https://ollama.ai" -ForegroundColor Yellow
        Write-Host "         Run: ollama pull llama3.2-vision" -ForegroundColor Gray
    }
}

# GPU
Write-Host ""
try {
    nvidia-smi 2>&1 | Out-Null
    Write-Host "  [OK] NVIDIA GPU - hardware encoding enabled" -ForegroundColor Green
} catch {
    Write-Host "  [INFO] No NVIDIA GPU - CPU encoding" -ForegroundColor Gray
}

# ── Create directories ───────────────────────────
@("media", "media\uploads", "media\output", "media\frames") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# ── Summary ──────────────────────────────────────
Write-Host ""
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Backend:   " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor White
Write-Host "   API docs:  " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "   Health:    " -NoNewline; Write-Host "http://localhost:8000/api/health" -ForegroundColor Gray
Write-Host ""
Write-Host "   Frontend:  " -NoNewline; Write-Host "https://moviecutter.web.app" -ForegroundColor White
Write-Host ""
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# ── Launch ───────────────────────────────────────
python -m uvicorn backend.src.adapters.inbound.fastapi_app:app --host 0.0.0.0 --port 8000 --reload
