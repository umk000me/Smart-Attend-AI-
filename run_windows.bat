@echo off
title SmartAttend AI — Launcher
color 0B

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║       SmartAttend AI — Windows Launcher      ║
echo  ║       Offline Lecture Attendance System      ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── Check Python ─────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% found

:: ── Create venv if needed ─────────────────────────────────────────────
if not exist "venv\" (
    echo  [SETUP] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created
)

:: ── Activate venv ─────────────────────────────────────────────────────
call venv\Scripts\activate.bat
echo  [OK] Virtual environment activated

:: ── Install core dependencies ─────────────────────────────────────────
echo.
echo  [SETUP] Checking / installing dependencies...
pip install Flask Werkzeug opencv-python numpy Pillow --quiet --no-warn-script-location
echo  [OK] Core packages ready (Flask, OpenCV, NumPy, Pillow)

:: ── Try face_recognition (optional) ──────────────────────────────────
python -c "import face_recognition" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [INFO] face_recognition not installed.
    echo         App will run in DEMO MODE ^(simulated face detection^).
    echo         To enable real face recognition, run install_face_recognition.bat
    echo.
) else (
    echo  [OK] face_recognition available - FULL AI MODE
)

:: ── Launch Flask ──────────────────────────────────────────────────────
echo.
echo  ══════════════════════════════════════════════
echo   Starting SmartAttend AI...
echo   Open browser: http://localhost:5000
echo   Press Ctrl+C to stop
echo  ══════════════════════════════════════════════
echo.

python app.py

echo.
echo  Server stopped. Press any key to exit.
pause >nul
