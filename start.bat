@echo off
chcp 65001 >nul
echo ========================================
echo  Auto-FPS-Clipper Pro v3.0
echo AI-Powered Professional Video Editor
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    echo [SETUP] Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo.
    echo [INFO] Dependencies installed!
    echo.
) else (
    call venv\Scripts\activate
)

echo [CHECK] System Requirements
echo.

REM Check Python version
python --version | findstr /C:"Python 3" >nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.8+ is required!
    pause
    exit /b 1
)
echo  Python version OK

REM Check FFmpeg
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] FFmpeg not found! Please install FFmpeg
    echo Download: https://ffmpeg.org/download.html
) else (
    echo  FFmpeg detected
)

REM Check Ollama connection
echo.
echo [CHECK] Ollama AI Server...
timeout /t 1 /nobreak >nul
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Ollama server is not running!
    echo Please start Ollama server: ollama serve
    echo Then run: ollama pull llama3.2-vision
    echo.
) else (
    echo  Ollama server connected
)

REM Check GPU (NVIDIA)
nvidia-smi >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo  NVIDIA GPU detected - Hardware acceleration enabled
) else (
    echo [INFO] No NVIDIA GPU detected - Using CPU encoding
)

echo.
echo ========================================
echo  Features Enabled:
echo ========================================
echo ✓ AI Video Analysis (Ollama)
echo ✓ Super Resolution Upscaling
echo ✓ Professional Color Grading
echo ✓ Audio Enhancement
echo ✓ Smart Cropping (9:16)
echo ✓ GPU Accelerated Encoding
echo ✓ Engagement Prediction
echo ✓ Auto Chapter Generation
echo ✓ Thumbnail A/B Testing
echo ========================================
echo.
echo [START] Launching Web Server...
echo.
echo  Open your browser and navigate to:
echo     http://localhost:8000
echo.
echo  Documentation: README.md
echo  Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

REM Start server with auto-reload
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

pause
