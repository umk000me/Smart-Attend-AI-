# SmartAttend AI — Windows Setup Guide

---

## ⚡ Quickest Start (2 steps)

**Step 1** — Make sure Python 3.8–3.12 is installed:
👉 https://www.python.org/downloads/windows/
☑ Check **"Add Python to PATH"** during install

**Step 2** — Double-click `run_windows.bat`

That's it. Opens at **http://localhost:5000**

---

## 🔑 Demo Login Credentials

| Role        | Email              | Password    |
|-------------|-------------------|-------------|
| Super Admin | admin@smart.edu   | admin123    |
| Faculty     | priya@smart.edu   | faculty123  |
| Faculty     | rahul@smart.edu   | faculty123  |

---

## 📁 Project Structure

```
smartattend\
├── run_windows.bat              ← Double-click to start
├── install_face_recognition.bat ← Optional: enable real AI
├── app.py                       ← Flask backend (1,100+ lines)
├── attendance.db                ← Auto-created SQLite database
├── requirements.txt
├── README_WINDOWS.md
├── student_images\              ← Drop face photos here
├── static\
│   ├── css\style.css
│   └── captured_images\         ← Lecture photos auto-saved here
└── templates\
    ├── login.html
    ├── admin_dashboard.html
    ├── add_student.html          ← Webcam face enrollment
    ├── add_faculty.html
    ├── faculty_dashboard.html
    ├── start_lecture.html
    ├── lecture_monitor.html      ← Live 3-capture UI
    ├── attendance_report.html
    ├── all_reports.html
    └── analytics.html
```

---

## 🤖 Two Modes

### Demo Mode (default — no extra install needed)
- App works **immediately** after `run_windows.bat`
- Face detection uses OpenCV Haar cascades
- Random students from DB are simulated as "detected"
- All attendance logic, images, analytics work perfectly
- Great for UI demo and testing the full workflow

### Full AI Mode (real face recognition)
- Double-click `install_face_recognition.bat`
- See face_recognition install section below
- Uses `face_recognition` library (dlib-based)
- Matches real faces from student enrollment photos

---

## 📸 Student Face Enrollment

1. Log in as **Super Admin** → **Student Enrollment**
2. Enter student name, roll number, department
3. Click **"Open Camera"** → **"Capture Face"**
4. Click **Register Student**
5. Face encoding is stored in the database

**OR** drop photos manually into `student_images\` folder:
- Filename: `ROLLNO.jpg` or `CS2401_Name.jpg`
- Then click **"Reload Face Engine"** on the enrollment page

---

## 🚀 Full Workflow

```
1. Admin logs in  →  Enrolls students with webcam
2. Faculty logs in  →  Starts Lecture  →  Selects subject
3. Browser activates webcam
4. Auto-captures at 0s / 20s / 40s
5. Each capture → face recognition → image saved
6. After capture 3 → attendance computed automatically:
     Present   = seen in 2 or 3 captures
     Late      = only seen in capture 3
     Early Exit= seen in 1 & 2, missing in 3
     Absent    = not seen at all
7. Faculty views report with image proof + analytics
```

---

## 🔧 face_recognition on Windows (Full AI Mode)

### Method A — Automatic (try first)
```
Double-click install_face_recognition.bat
```

### Method B — Pre-built dlib wheel (most reliable)
1. Go to: https://github.com/z-mahmud22/Dlib_Windows_Python3.x/releases
2. Download the `.whl` matching your Python:
   - Python 3.9  → `dlib-19.24.2-cp39-cp39-win_amd64.whl`
   - Python 3.10 → `dlib-19.24.2-cp310-cp310-win_amd64.whl`
   - Python 3.11 → `dlib-19.24.2-cp311-cp311-win_amd64.whl`
   - Python 3.12 → `dlib-19.24.2-cp312-cp312-win_amd64.whl`
3. Open Command Prompt in the project folder:
   ```
   venv\Scripts\activate
   pip install path\to\dlib-19.24.2-cpXX-cpXX-win_amd64.whl
   pip install face_recognition
   ```
4. Run `run_windows.bat`

### Method C — Visual Studio Build Tools (compile from source)
1. Install: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Select workload: **"Desktop development with C++"**
3. Then run `install_face_recognition.bat`

---

## 🖥 Manual Command Line (if .bat doesn't work)

```cmd
:: Open Command Prompt in the project folder
cd path\to\smartattend

:: Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

:: Install packages
pip install Flask Werkzeug opencv-python numpy Pillow

:: Run the app
python app.py
```

---

## ❓ Common Windows Issues

| Problem | Fix |
|---------|-----|
| `python` not recognized | Re-install Python, check "Add to PATH" |
| Camera not opening | Allow camera in Windows Settings → Privacy → Camera |
| Port 5000 in use | Edit `app.py` last line: `port=5001` |
| `pip` not found | Run: `python -m pip install ...` |
| Blank page on login | Try Chrome or Edge (not IE) |
| `dlib` build fails | Use Method B (pre-built wheel) above |

---

## 📊 Analytics Features

| Metric | Formula |
|--------|---------|
| **Attendance %** | attended / total × 100 |
| **Velocity Index** | this_week_attended − last_week_attended |
| **Risk Countdown** | max misses before dropping below 75% |
| **Predicted %** | linear regression over weekly buckets |

---

*SmartAttend AI · Windows Edition · v2.0 · 100% Offline*
