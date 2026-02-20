@echo off
chcp 65001 >nul
title ClipMontage Local Server

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     ClipMontage - Local Environment      ║
echo  ║   AI Video Montage Generation Platform   ║
echo  ╚══════════════════════════════════════════╝
echo.

REM ── Configuration ──────────────────────────────
set APP_ENV=development
set PERSISTENCE_BACKEND=memory
set FIREBASE_ENABLED=true
set FIREBASE_PROJECT_ID=moviecutter
set FIREBASE_AUTH_DOMAIN=moviecutter.firebaseapp.com
set FIREBASE_API_KEY=AIzaSyA1w0t5mlM8bH0RHd1Dp6Ziins32_thAM0
set GCS_ENABLED=false
set ALLOWED_ORIGIN=*

REM ── Firebase SA key (set path if you have one) ─
if exist "moviecutter-firebase-adminsdk-fbsvc-*.json" (
    for %%f in (moviecutter-firebase-adminsdk-fbsvc-*.json) do set FIREBASE_CREDENTIALS_PATH=%%f
    echo  [OK] Firebase SA key found: %FIREBASE_CREDENTIALS_PATH%
) else (
    echo  [WARN] Firebase SA key not found in project root
    echo         Auth token verification will fail.
    echo         Place your firebase-adminsdk JSON file here.
    echo.
)

REM ── Virtual environment ─────────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate
    echo  [OK] Virtual environment: .venv
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
    echo  [OK] Virtual environment: venv
) else (
    echo  [SETUP] Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    echo  [SETUP] Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo.
)

REM ── System checks ───────────────────────────────
echo.
echo  ── System Check ──────────────────────────
echo.

REM Python
python --version 2>nul | findstr /C:"Python 3" >nul
if %ERRORLEVEL% neq 0 (
    echo  [FAIL] Python 3.x required
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK] %%v

REM FFmpeg
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [FAIL] FFmpeg not found! Install from https://ffmpeg.org/download.html
    pause
    exit /b 1
) else (
    echo  [OK] FFmpeg installed
)

REM Ollama
echo.
echo  ── Ollama AI Server ──────────────────────
echo.
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [WARN] Ollama is not running!
    echo.
    echo         Start Ollama:  ollama serve
    echo         Pull model:    ollama pull llama3.2-vision
    echo.
    echo         Starting Ollama in background...
    start /min "Ollama" ollama serve
    timeout /t 3 /nobreak >nul
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo  [WARN] Could not start Ollama automatically.
        echo         Video processing will fail without AI model.
    ) else (
        echo  [OK] Ollama started successfully
    )
) else (
    echo  [OK] Ollama server running
    REM Show available models
    for /f "delims=" %%m in ('curl -s http://localhost:11434/api/tags 2^>nul ^| python -c "import sys,json; [print(f\"         - {m['name']}\") for m in json.load(sys.stdin).get('models',[])]" 2^>nul') do echo %%m
)

REM GPU
echo.
nvidia-smi >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo  [OK] NVIDIA GPU detected - hardware encoding enabled
) else (
    echo  [INFO] No NVIDIA GPU - using CPU encoding
)

REM ── Create media directories ────────────────────
if not exist "media" mkdir media
if not exist "media\uploads" mkdir media\uploads
if not exist "media\output" mkdir media\output
if not exist "media\frames" mkdir media\frames

REM ── Launch ──────────────────────────────────────
echo.
echo  ══════════════════════════════════════════
echo.
echo   Backend:   http://localhost:8000
echo   API docs:  http://localhost:8000/docs
echo   Health:    http://localhost:8000/api/health
echo.
echo   Frontend:  https://moviecutter.web.app
echo              (or open static/index.html locally)
echo.
echo   Press Ctrl+C to stop
echo.
echo  ══════════════════════════════════════════
echo.

python -m uvicorn backend.src.adapters.inbound.fastapi_app:app --host 0.0.0.0 --port 8000 --reload

pause
