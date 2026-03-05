@echo off
title SmartAttend AI — Install Face Recognition
color 0E

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║   face_recognition Installer for Windows         ║
echo  ║   Uses pre-built dlib wheel (no cmake needed!)   ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  This installs real AI face recognition.
echo  The app already works without it (DEMO MODE).
echo.

:: Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated
) else (
    echo  [WARN] No venv found — installing to system Python
)

:: Detect Python version for correct dlib wheel
for /f "tokens=1,2 delims=." %%a in ('python -c "import sys; print(sys.version[:3])"') do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
echo  [INFO] Python version: %PY_MAJOR%.%PY_MINOR%

echo.
echo  [STEP 1] Installing cmake...
pip install cmake --quiet
echo  [OK] cmake installed

echo.
echo  [STEP 2] Trying to install dlib (pre-built wheel)...
echo  This may take 1-5 minutes...

:: Try the unofficial pre-built wheels first (much faster, no compile needed)
pip install dlib --quiet 2>nul
if errorlevel 1 (
    echo  [INFO] Standard dlib install failed — trying pre-built wheel...
    echo.
    echo  ──────────────────────────────────────────────────────
    echo  MANUAL STEP REQUIRED:
    echo.
    echo  1. Go to: https://github.com/z-mahmud22/Dlib_Windows_Python3.x
    echo  2. Download the .whl file matching your Python version:
    echo     Python 3.8  →  dlib-19.24.2-cp38-cp38-win_amd64.whl
    echo     Python 3.9  →  dlib-19.24.2-cp39-cp39-win_amd64.whl
    echo     Python 3.10 →  dlib-19.24.2-cp310-cp310-win_amd64.whl
    echo     Python 3.11 →  dlib-19.24.2-cp311-cp311-win_amd64.whl
    echo     Python 3.12 →  dlib-19.24.2-cp312-cp312-win_amd64.whl
    echo  3. Run: pip install path\to\downloaded.whl
    echo  4. Then run this script again.
    echo  ──────────────────────────────────────────────────────
    echo.
    echo  OR install Visual Studio Build Tools:
    echo  https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo  Select: "Desktop development with C++"
    echo  Then re-run this script.
    echo.
    pause
    exit /b 1
)

echo  [OK] dlib installed

echo.
echo  [STEP 3] Installing face_recognition...
pip install face_recognition --quiet
if errorlevel 1 (
    echo  [ERROR] face_recognition install failed.
    pause
    exit /b 1
)

echo  [OK] face_recognition installed!
echo.
echo  ══════════════════════════════════════════════
echo   Full AI Face Recognition is now ENABLED.
echo   Run the app: run_windows.bat
echo  ══════════════════════════════════════════════
echo.
pause
