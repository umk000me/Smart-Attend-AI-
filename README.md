# SmartAttend AI — Lecture Attendance System

> AI-powered lecture-wise attendance monitoring with face recognition,
> anti-spoofing, and predictive analytics. **100% offline.**

---

## ⚡ Quick Start

```bash
# 1. Clone / download project
cd smartattend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install Flask Werkzeug opencv-python numpy Pillow

# 4. (Optional but recommended) Install face_recognition
#    Requires cmake + dlib:
pip install cmake dlib face_recognition

# 5. Run
python app.py
```

Open **http://localhost:5000**

---

## 🔑 Demo Credentials

| Role        | Email              | Password    |
|-------------|-------------------|-------------|
| Super Admin | admin@smart.edu   | admin123    |
| Faculty     | priya@smart.edu   | faculty123  |
| Faculty     | rahul@smart.edu   | faculty123  |
| Faculty     | meena@smart.edu   | faculty123  |

---

## 🗂 File Structure

```
smartattend/
├── app.py                      ← Flask backend (all routes + logic)
├── attendance.db               ← SQLite DB (auto-created on first run)
├── requirements.txt
├── README.md
├── student_images/             ← Student face photos (JPG/PNG)
├── static/
│   ├── css/style.css           ← Dark cyberpunk stylesheet
│   └── captured_images/        ← Lecture capture images (auto-saved)
└── templates/
    ├── base.html               ← Sidebar + topbar shell
    ├── login.html
    ├── admin_dashboard.html
    ├── add_student.html        ← Face enrollment with webcam capture
    ├── add_faculty.html
    ├── faculty_dashboard.html
    ├── start_lecture.html
    ├── lecture_monitor.html    ← Real-time capture UI
    ├── attendance_report.html  ← Per-lecture report with images
    ├── all_reports.html        ← Admin: all lectures
    └── analytics.html          ← Velocity, Risk, Predictions
```

---

## 🎓 Full Workflow

```
Super Admin
  └─ Enroll Students (/admin/add_student)
       • Enter name, roll number, department
       • Click "Open Camera" → "Capture Face"
       • Face encoding saved to DB as BLOB
       
Faculty
  └─ Login → Start Lecture (/faculty/start_lecture)
       • Select subject + room
       • Camera activates automatically
       
Lecture Monitor (/faculty/lecture/<id>/monitor)
  └─ Capture 1 at 0s  → face recognition → save image
  └─ Capture 2 at 20s → face recognition → save image
  └─ Capture 3 at 40s → face recognition → save image
  └─ Auto compute attendance:
       Present   = detected in 2 or 3 captures
       Late      = only detected in capture 3
       Early Exit= present in 1 & 2, missing in 3
       Absent    = not detected at all
       
Attendance Report (/faculty/attendance/<id>)
  └─ Summary cards + image proof + student table
  
Analytics (/faculty/analytics)
  └─ Velocity Index  = this_week_attended − last_week_attended
  └─ Risk Countdown  = max misses before dropping below 75%
  └─ Predicted %     = linear regression on weekly data
```

---

## 🤖 Demo Mode (No face_recognition)

If `face_recognition` is not installed, the app runs in **DEMO MODE**:
- Haar cascade detects faces in the frame
- Random students from the DB are assigned as "detected"
- All attendance logic, DB saving, and analytics work normally
- Perfect for UI/workflow demonstration

---

## 📦 face_recognition Install (Ubuntu/macOS)

```bash
# Ubuntu
sudo apt-get install cmake libboost-all-dev
pip install dlib face_recognition

# macOS
brew install cmake boost
pip install dlib face_recognition
```

---

## 📸 Adding Student Photos Manually

Drop face images in `student_images/` named as `Roll_No.jpg`  
e.g., `CS2401.jpg` or `CS2401_Aarav_Singh.jpg`

Then visit: **Admin → Student Enrollment → Reload Face Engine**

---

## 🛡 Anti-Spoofing

Basic frame-diff analysis detects:
- Static printed photos (near-zero frame difference)
- Repeated identical frames

Flagged students get `spoof_flag = 1` in the attendance table.

---

*SmartAttend AI · Offline Edition · v2.0*
