"""
SmartAttend AI — Complete Lecture Attendance System
====================================================
Run:  python app.py
URL:  http://localhost:5000

Demo logins:
  Super Admin  →  admin@smart.edu   / admin123
  Faculty      →  priya@smart.edu   / faculty123
               →  rahul@smart.edu   / faculty123
"""

# ─────────────────────────────────────────────────────────────────────────────
#  IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import os, sys, cv2, time, sqlite3, pickle, threading, base64, json, re
from typing import Optional, List, Dict, Tuple
import numpy as np
from datetime import datetime, date, timedelta
from io import BytesIO
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, Response)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Face recognition — graceful fallback to demo mode
try:
    import face_recognition
    FR_AVAILABLE = True
    print("✓  face_recognition loaded")
except ImportError:
    FR_AVAILABLE = False
    print("⚠  face_recognition not found — DEMO mode (random simulation)")

# ─────────────────────────────────────────────────────────────────────────────
#  APP CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartattend_ai_2024_secret_key_xyz")

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
DATABASE           = os.path.join(BASE_DIR, "attendance.db")
STUDENT_IMAGES_DIR = os.path.join(BASE_DIR, "student_images")
CAPTURED_DIR       = os.path.join(BASE_DIR, "static", "captured_images")
ALLOWED_IMG_EXT    = {"jpg", "jpeg", "png"}

# Capture schedule in seconds after lecture start (demo: 0 / 20 / 40 s)
CAPTURE_SCHEDULE = [0, 20, 40]

os.makedirs(STUDENT_IMAGES_DIR, exist_ok=True)
os.makedirs(CAPTURED_DIR,       exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
#  IN-MEMORY STORES
# ─────────────────────────────────────────────────────────────────────────────
known_encodings: list = []   # parallel lists
known_names:     list = []
active_lectures: dict = {}   # lecture_id (int) → LectureSession
_lock = threading.Lock()


# ═════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ═════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables and seed demo data on first run."""
    conn = get_db()
    cur  = conn.cursor()

    cur.executescript("""
    -- ── users ─────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT    NOT NULL,
        email         TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        role          TEXT    NOT NULL DEFAULT 'faculty',
        subject       TEXT,
        department    TEXT,
        created_at    TEXT    DEFAULT (date('now'))
    );

    -- ── students ───────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS students (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no        TEXT    NOT NULL UNIQUE,
        name           TEXT    NOT NULL,
        department     TEXT,
        encoding_blob  BLOB,
        photo_path     TEXT,
        created_at     TEXT    DEFAULT (date('now'))
    );

    -- ── timetable ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS timetable (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id  INTEGER NOT NULL,
        subject     TEXT    NOT NULL,
        day_of_week TEXT    NOT NULL,
        start_time  TEXT    NOT NULL,
        end_time    TEXT    NOT NULL,
        FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── lectures ───────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS lectures (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id  INTEGER NOT NULL,
        subject     TEXT    NOT NULL,
        date        TEXT    NOT NULL,
        start_time  TEXT    NOT NULL,
        end_time    TEXT,
        room        TEXT    DEFAULT 'Lab-1',
        status      TEXT    NOT NULL DEFAULT 'active',
        FOREIGN KEY(faculty_id) REFERENCES users(id)
    );

    -- ── attendance ─────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS attendance (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        lecture_id      INTEGER NOT NULL,
        student_roll    TEXT    NOT NULL,
        student_name    TEXT    NOT NULL,
        subject         TEXT    NOT NULL,
        date            TEXT    NOT NULL,
        capture1        INTEGER NOT NULL DEFAULT 0,
        capture2        INTEGER NOT NULL DEFAULT 0,
        capture3        INTEGER NOT NULL DEFAULT 0,
        final_status    TEXT    NOT NULL DEFAULT 'Absent',
        late_flag       INTEGER NOT NULL DEFAULT 0,
        early_exit_flag INTEGER NOT NULL DEFAULT 0,
        spoof_flag      INTEGER NOT NULL DEFAULT 0,
        image1_path     TEXT,
        image2_path     TEXT,
        image3_path     TEXT,
        FOREIGN KEY(lecture_id) REFERENCES lectures(id)
    );
    """)

    # Seed only if no admin exists
    existing = cur.execute(
        "SELECT id FROM users WHERE role='super_admin'"
    ).fetchone()

    if not existing:
        _seed_demo_data(cur)

    conn.commit()
    conn.close()
    print("✓  Database ready")


def _seed_demo_data(cur):
    """Insert demo users, students, timetable, and 4 weeks of attendance."""
    import random

    # ── Users ──────────────────────────────────────────────────────────────
    users = [
        ("Super Admin",     "admin@smart.edu",  "admin123",    "super_admin", "All",                "Administration"),
        ("Dr. Priya Sharma","priya@smart.edu",  "faculty123",  "faculty",     "Machine Learning",   "Computer Science"),
        ("Prof. Rahul Verma","rahul@smart.edu", "faculty123",  "faculty",     "Data Structures",    "Computer Science"),
        ("Dr. Meena Iyer",  "meena@smart.edu",  "faculty123",  "faculty",     "Computer Networks",  "Computer Science"),
    ]
    for name, email, pwd, role, subj, dept in users:
        cur.execute("""
            INSERT OR IGNORE INTO users
            (name, email, password_hash, role, subject, department)
            VALUES (?,?,?,?,?,?)
        """, (name, email, generate_password_hash(pwd), role, subj, dept))

    # ── Students ───────────────────────────────────────────────────────────
    students = [
        ("CS2401","Aarav Singh",    "Computer Science"),
        ("CS2402","Priya Patel",    "Computer Science"),
        ("CS2403","Rohan Mehta",    "Computer Science"),
        ("CS2404","Ananya Kumar",   "Computer Science"),
        ("CS2405","Vikram Joshi",   "Computer Science"),
        ("CS2406","Neha Gupta",     "Computer Science"),
        ("CS2407","Arjun Nair",     "Computer Science"),
        ("CS2408","Kavya Reddy",    "Computer Science"),
        ("CS2409","Siddharth Rao",  "Computer Science"),
        ("CS2410","Divya Mishra",   "Computer Science"),
        ("CS2411","Karan Shah",     "Computer Science"),
        ("CS2412","Riya Verma",     "Computer Science"),
    ]
    for roll, name, dept in students:
        cur.execute("""
            INSERT OR IGNORE INTO students (roll_no, name, department)
            VALUES (?,?,?)
        """, (roll, name, dept))

    # ── Timetable ──────────────────────────────────────────────────────────
    timetable = [
        (2, "Machine Learning",  "Monday",    "09:00","10:00"),
        (2, "Machine Learning",  "Wednesday", "11:00","12:00"),
        (2, "Machine Learning",  "Friday",    "14:00","15:00"),
        (3, "Data Structures",   "Tuesday",   "10:00","11:00"),
        (3, "Data Structures",   "Thursday",  "13:00","14:00"),
        (4, "Computer Networks", "Monday",    "14:00","15:00"),
        (4, "Computer Networks", "Friday",    "09:00","10:00"),
    ]
    for fid, subj, day, st, et in timetable:
        cur.execute("""
            INSERT INTO timetable
            (faculty_id, subject, day_of_week, start_time, end_time)
            VALUES (?,?,?,?,?)
        """, (fid, subj, day, st, et))

    # ── Attendance History (4 weeks) ────────────────────────────────────────
    today = date.today()
    student_list = [(r, n) for r, n, _ in students]

    for weeks_back in range(1, 5):
        for day_offset in [0, 2, 4]:   # Mon/Wed/Fri pattern
            lec_date = today - timedelta(weeks=weeks_back, days=day_offset)
            # Machine Learning lecture
            cur.execute("""
                INSERT INTO lectures
                (faculty_id, subject, date, start_time, end_time, status)
                VALUES (2,'Machine Learning',?,?,?,'completed')
            """, (lec_date.isoformat(), "09:00", "10:00"))
            lid = cur.lastrowid

            for roll, name in student_list:
                r = random.random()
                if   r < 0.65:  c1,c2,c3,fs,lf,ef = 1,1,1,"Present",    0,0
                elif r < 0.75:  c1,c2,c3,fs,lf,ef = 0,0,1,"Late",       1,0
                elif r < 0.85:  c1,c2,c3,fs,lf,ef = 1,1,0,"Early Exit", 0,1
                else:           c1,c2,c3,fs,lf,ef = 0,0,0,"Absent",     0,0

                cur.execute("""
                    INSERT INTO attendance
                    (lecture_id,student_roll,student_name,subject,date,
                     capture1,capture2,capture3,final_status,
                     late_flag,early_exit_flag,spoof_flag)
                    VALUES (?,?,?,'Machine Learning',?,?,?,?,?,?,?,0)
                """, (lid, roll, name, lec_date.isoformat(),
                      c1, c2, c3, fs, lf, ef))


# ═════════════════════════════════════════════════════════════════════════════
#  FACE RECOGNITION ENGINE
# ═════════════════════════════════════════════════════════════════════════════

def load_known_faces():
    """Load face encodings from DB + student_images folder into memory."""
    global known_encodings, known_names
    known_encodings.clear()
    known_names.clear()

    conn = get_db()
    rows = conn.execute(
        "SELECT name, roll_no, encoding_blob FROM students"
    ).fetchall()
    conn.close()

    # Load from DB blobs
    for row in rows:
        if row["encoding_blob"]:
            try:
                enc = pickle.loads(row["encoding_blob"])
                known_encodings.append(enc)
                known_names.append(row["name"])
            except Exception:
                pass

    if not FR_AVAILABLE:
        print(f"  Demo mode: {len(known_names)} stubs from DB")
        return

    # Also scan student_images folder for any loose JPG/PNG
    for fname in os.listdir(STUDENT_IMAGES_DIR):
        if fname.lower().split(".")[-1] in ALLOWED_IMG_EXT:
            student_name = os.path.splitext(fname)[0].replace("_", " ").title()
            if student_name not in known_names:
                try:
                    img  = face_recognition.load_image_file(
                               os.path.join(STUDENT_IMAGES_DIR, fname))
                    encs = face_recognition.face_encodings(img)
                    if encs:
                        known_encodings.append(encs[0])
                        known_names.append(student_name)
                except Exception as e:
                    print(f"  ⚠ encode error {fname}: {e}")

    print(f"✓  {len(known_names)} faces loaded")


def encode_student_image(image_path: str):
    """Return face encoding for a single image, or None."""
    if not FR_AVAILABLE:
        return None
    try:
        img  = face_recognition.load_image_file(image_path)
        encs = face_recognition.face_encodings(img)
        return encs[0] if encs else None
    except Exception:
        return None


def recognize_faces(frame_bgr: np.ndarray) -> Tuple[List[str], np.ndarray]:
    """
    Returns (detected_names, annotated_frame).
    Falls back to Haar + simulated names in demo mode.
    """
    annotated = frame_bgr.copy()
    _draw_hud(annotated)

    if FR_AVAILABLE and known_encodings:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locs  = face_recognition.face_locations(rgb, model="hog")
        encs  = face_recognition.face_encodings(rgb, locs)
        names = []
        for enc, (top,right,bottom,left) in zip(encs, locs):
            dists   = face_recognition.face_distance(known_encodings, enc)
            best    = int(np.argmin(dists))
            matched = known_names[best] if dists[best] < 0.55 else "Unknown"
            names.append(matched)
            # Draw box
            color = (0, 255, 128) if matched != "Unknown" else (0, 80, 255)
            cv2.rectangle(annotated, (left,top), (right,bottom), color, 2)
            cv2.rectangle(annotated, (left,bottom-22), (right,bottom), color, cv2.FILLED)
            cv2.putText(annotated, matched, (left+4, bottom-6),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, (0,0,0), 1)
        return list(set(n for n in names if n != "Unknown")), annotated

    # ── Demo mode: Haar cascades + random student names ─────────────────────
    return _demo_recognize(frame_bgr, annotated)


def _demo_recognize(frame_bgr: np.ndarray,
                    annotated: np.ndarray) -> Tuple[List[str], np.ndarray]:
    import random
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    fc  = cv2.CascadeClassifier(cascade)
    boxes = fc.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))

    conn  = get_db()
    pool  = [r["name"] for r in conn.execute("SELECT name FROM students").fetchall()]
    conn.close()

    n = max(len(boxes), random.randint(4, min(9, len(pool))))
    detected = random.sample(pool, min(n, len(pool)))

    for i, (x, y, w, h) in enumerate(boxes[:len(detected)]):
        name = detected[i]
        cv2.rectangle(annotated, (x,y), (x+w,y+h), (0,255,128), 2)
        cv2.rectangle(annotated, (x,y+h-22), (x+w,y+h), (0,255,128), cv2.FILLED)
        cv2.putText(annotated, name[:14], (x+4, y+h-6),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, (0,0,0), 1)
    return detected, annotated


def _draw_hud(frame: np.ndarray):
    """Overlay timestamp + system label on frame."""
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(frame, f"SmartAttend AI | {ts}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 180), 2)
    cv2.putText(frame, "FACE RECOGNITION ACTIVE",
                (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (0, 200, 255), 1)


def detect_spoof(prev: Optional[np.ndarray], curr: np.ndarray) -> bool:
    """Basic anti-spoof: static image detection via frame diff."""
    if prev is None:
        return False
    if prev.shape != curr.shape:
        return False
    diff = cv2.absdiff(prev, curr)
    return float(np.mean(diff)) < 1.2   # near-zero → static/spoofed


# ═════════════════════════════════════════════════════════════════════════════
#  LECTURE SESSION
# ═════════════════════════════════════════════════════════════════════════════

class LectureSession:
    def __init__(self, lecture_id: int, subject: str, faculty_id: int):
        self.lecture_id  = lecture_id
        self.subject     = subject
        self.faculty_id  = faculty_id
        self.started_at  = time.time()
        self.captures:   dict = {}   # 1/2/3 → {names, path, spoof}
        self.prev_frame: Optional[np.ndarray] = None
        self.spoof_set:  set = set()
        self.status      = "active"
        self._lock       = threading.Lock()

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def next_capture(self) -> Optional[int]:
        for i, t in enumerate(CAPTURE_SCHEDULE, 1):
            if i not in self.captures and self.elapsed >= t:
                return i
        return None

    def next_in(self) -> Optional[float]:
        for i, t in enumerate(CAPTURE_SCHEDULE, 1):
            if i not in self.captures:
                return max(0.0, round(t - self.elapsed, 1))
        return None

    def is_complete(self) -> bool:
        return len(self.captures) >= 3

    def to_dict(self) -> dict:
        return {
            "lecture_id": self.lecture_id,
            "subject":    self.subject,
            "elapsed":    round(self.elapsed, 1),
            "status":     self.status,
            "captures":   {k: {"names": v["names"], "path": v["path"],
                               "spoof": v["spoof"]}
                           for k, v in self.captures.items()},
            "next_in":    self.next_in(),
            "complete":   self.is_complete(),
        }

# ═════════════════════════════════════════════════════════════════════════════
#  ATTENDANCE LOGIC
# ═════════════════════════════════════════════════════════════════════════════

def compute_attendance(ls: LectureSession):
    """Write final attendance records to DB after all 3 captures."""
    conn = get_db()
    cur  = conn.cursor()

    c1 = set(ls.captures.get(1, {}).get("names", []))
    c2 = set(ls.captures.get(2, {}).get("names", []))
    c3 = set(ls.captures.get(3, {}).get("names", []))

    students = cur.execute(
        "SELECT roll_no, name FROM students"
    ).fetchall()

    today = date.today().isoformat()

    for s in students:
        roll = s["roll_no"];  name = s["name"]
        d1 = 1 if name in c1 else 0
        d2 = 1 if name in c2 else 0
        d3 = 1 if name in c3 else 0
        total = d1 + d2 + d3
        lf = ef = 0

        if total >= 2:
            status = "Present"
        elif d3 == 1 and total == 1:
            status = "Late";        lf = 1
        elif d3 == 0 and total >= 1:
            status = "Early Exit";  ef = 1
        else:
            status = "Absent"

        spoof = 1 if name in ls.spoof_set else 0
        p = {i: ls.captures.get(i, {}).get("path", "") for i in range(1,4)}

        cur.execute("""
            INSERT OR REPLACE INTO attendance
            (lecture_id, student_roll, student_name, subject, date,
             capture1, capture2, capture3,
             final_status, late_flag, early_exit_flag, spoof_flag,
             image1_path, image2_path, image3_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ls.lecture_id, roll, name, ls.subject, today,
              d1, d2, d3, status, lf, ef, spoof,
              p[1], p[2], p[3]))

    cur.execute("""
        UPDATE lectures SET status='completed', end_time=? WHERE id=?
    """, (datetime.now().strftime("%H:%M"), ls.lecture_id))

    conn.commit()
    conn.close()
    print(f"✓  Lecture {ls.lecture_id} attendance saved")


# ═════════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════

def get_student_analytics(student_name: str, subject: str = None) -> dict:
    conn = get_db()
    q    = "SELECT * FROM attendance WHERE student_name=?"
    p    = [student_name]
    if subject:
        q += " AND subject=?";  p.append(subject)
    rows = conn.execute(q + " ORDER BY date ASC", p).fetchall()
    conn.close()

    total    = len(rows)
    present  = sum(1 for r in rows if r["final_status"] == "Present")
    late     = sum(1 for r in rows if r["final_status"] == "Late")
    early    = sum(1 for r in rows if r["final_status"] == "Early Exit")
    absent   = sum(1 for r in rows if r["final_status"] == "Absent")
    attended = present + late + early
    pct      = round(attended / total * 100, 1) if total else 0.0

    # Velocity: this week attended − missed vs last week
    now = date.today()
    wk1 = [r for r in rows if (now - date.fromisoformat(r["date"])).days <  7]
    wk2 = [r for r in rows if 7 <= (now - date.fromisoformat(r["date"])).days < 14]
    velocity = (sum(1 for r in wk1 if r["final_status"] != "Absent") -
                sum(1 for r in wk2 if r["final_status"] != "Absent"))

    # Risk countdown: max misses before dropping below 75 %
    # (attended)/(total+m) >= 0.75  →  m ≤ (4*attended - 3*total) / 3
    risk = max(0, int((4 * attended - 3 * total) / 3)) if total else 0

    # Predictive trend (linear projection over weekly buckets)
    weekly: dict = {}
    for r in rows:
        wk = date.fromisoformat(r["date"]).isocalendar()[1]
        weekly.setdefault(wk, {"t": 0, "a": 0})
        weekly[wk]["t"] += 1
        if r["final_status"] != "Absent":
            weekly[wk]["a"] += 1
    pts = [round(v["a"] / v["t"] * 100, 1) for v in weekly.values() if v["t"]]

    if len(pts) >= 2:
        n   = len(pts);  xs = list(range(n))
        sx  = sum(xs);   sy = sum(pts)
        sxy = sum(x*y for x,y in zip(xs,pts))
        sx2 = sum(x*x for x in xs)
        denom = n*sx2 - sx*sx
        slope = (n*sxy - sx*sy) / denom if denom else 0
        predicted = round(max(0, min(100, pts[-1] + slope*4)), 1)
    else:
        predicted = pct

    return {
        "name": student_name, "total": total,
        "present": present, "late": late,
        "early_exit": early, "absent": absent,
        "attended": attended, "percentage": pct,
        "velocity": velocity, "risk": risk,
        "predicted": predicted, "trend": pts,
        "at_risk": pct < 75,
    }


def get_lecture_summary(lecture_id: int) -> dict:
    conn = get_db()
    att  = conn.execute(
        "SELECT * FROM attendance WHERE lecture_id=? ORDER BY student_name",
        (lecture_id,)
    ).fetchall()
    lec  = conn.execute(
        "SELECT l.*, u.name as faculty_name FROM lectures l "
        "JOIN users u ON l.faculty_id=u.id WHERE l.id=?", (lecture_id,)
    ).fetchone()
    conn.close()

    rows    = [dict(r) for r in att]
    total   = len(rows)
    present = sum(1 for r in rows if r["final_status"] == "Present")
    late    = sum(1 for r in rows if r["final_status"] == "Late")
    early   = sum(1 for r in rows if r["final_status"] == "Early Exit")
    absent  = sum(1 for r in rows if r["final_status"] == "Absent")
    pct     = round((present+late+early)/total*100, 1) if total else 0

    images = {}
    if rows:
        images = {
            1: rows[0].get("image1_path",""),
            2: rows[0].get("image2_path",""),
            3: rows[0].get("image3_path",""),
        }

    return {
        "lecture": dict(lec) if lec else {},
        "rows": rows,
        "total": total, "present": present,
        "late": late, "early_exit": early,
        "absent": absent, "pct": pct,
        "images": images,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ═════════════════════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if "uid" not in session:
            flash("Please log in.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapped


def roles(*allowed):
    def decorator(f):
        @wraps(f)
        def wrapped(*a, **kw):
            if session.get("role") not in allowed:
                flash("Access denied.", "danger")
                return redirect(url_for("index"))
            return f(*a, **kw)
        return wrapped
    return decorator


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTES — AUTH
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "uid" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("admin_dashboard") if session["role"] == "super_admin"
                    else url_for("faculty_dashboard"))


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw    = request.form.get("password","")
        conn  = get_db()
        user  = conn.execute(
            "SELECT * FROM users WHERE LOWER(email)=?", (email,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], pw):
            session.update({
                "uid":     user["id"],
                "uname":   user["name"],
                "role":    user["role"],
                "subject": user["subject"] or "",
            })
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out successfully.", "info")
    return redirect(url_for("login"))


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTES — SUPER ADMIN
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin/dashboard")
@login_required
@roles("super_admin")
def admin_dashboard():
    conn = get_db()
    faculty  = conn.execute("SELECT * FROM users WHERE role='faculty'").fetchall()
    stu_cnt  = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    lec_cnt  = conn.execute("SELECT COUNT(*) FROM lectures").fetchone()[0]
    today_lec= conn.execute("""
        SELECT l.*, u.name as fname FROM lectures l
        JOIN users u ON l.faculty_id=u.id
        WHERE l.date=? ORDER BY l.start_time
    """, (date.today().isoformat(),)).fetchall()

    # Overall today attendance summary
    today_att = conn.execute("""
        SELECT final_status, COUNT(*) as cnt
        FROM attendance WHERE date=?
        GROUP BY final_status
    """, (date.today().isoformat(),)).fetchall()
    att_map = {r["final_status"]: r["cnt"] for r in today_att}

    conn.close()
    return render_template("admin_dashboard.html",
        faculty=faculty, stu_cnt=stu_cnt, lec_cnt=lec_cnt,
        today_lec=today_lec, att_map=att_map,
        active_cnt=len(active_lectures))


@app.route("/admin/add_faculty", methods=["GET","POST"])
@login_required
@roles("super_admin")
def add_faculty():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action","add")
        if action == "add":
            data = (request.form["name"], request.form["email"],
                    generate_password_hash(request.form["password"]),
                    "faculty",
                    request.form.get("subject",""),
                    request.form.get("department",""))
            try:
                conn.execute("""
                    INSERT INTO users (name,email,password_hash,role,subject,department)
                    VALUES (?,?,?,?,?,?)
                """, data)
                conn.commit()
                flash(f"Faculty {request.form['name']} added.", "success")
            except sqlite3.IntegrityError:
                flash("Email already exists.", "danger")
        elif action == "delete":
            uid = request.form.get("uid")
            conn.execute("DELETE FROM users WHERE id=? AND role='faculty'", (uid,))
            conn.commit()
            flash("Faculty removed.", "info")
        elif action == "assign":
            uid  = request.form.get("uid")
            subj = request.form.get("subject","")
            conn.execute("UPDATE users SET subject=? WHERE id=?", (subj, uid))
            conn.commit()
            flash("Subject assigned.", "success")

    faculty = conn.execute("SELECT * FROM users WHERE role='faculty'").fetchall()
    conn.close()
    return render_template("add_faculty.html", faculty=faculty)


@app.route("/admin/add_student", methods=["GET","POST"])
@login_required
@roles("super_admin")
def add_student():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action","add")

        if action == "add":
            name   = request.form["name"].strip()
            roll   = request.form["roll_no"].strip().upper()
            dept   = request.form.get("department","Computer Science")
            imgb64 = request.form.get("face_image","")

            photo_path    = None
            encoding_blob = None

            if imgb64:
                try:
                    img_data = base64.b64decode(imgb64.split(",")[-1])
                    np_arr   = np.frombuffer(img_data, np.uint8)
                    frame    = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    fname    = f"{secure_filename(roll)}_{int(time.time())}.jpg"
                    fpath    = os.path.join(STUDENT_IMAGES_DIR, fname)
                    cv2.imwrite(fpath, frame)
                    photo_path = fname

                    enc = encode_student_image(fpath)
                    if enc is not None:
                        encoding_blob = pickle.dumps(enc)
                except Exception as e:
                    flash(f"Face capture error: {e}", "warning")

            try:
                conn.execute("""
                    INSERT INTO students
                    (roll_no, name, department, encoding_blob, photo_path)
                    VALUES (?,?,?,?,?)
                """, (roll, name, dept, encoding_blob, photo_path))
                conn.commit()
                load_known_faces()   # refresh in-memory
                msg = "Student registered"
                msg += " with face encoding." if encoding_blob else " (no face captured — add photo later)."
                flash(msg, "success")
            except sqlite3.IntegrityError:
                flash(f"Roll {roll} already exists.", "danger")

        elif action == "delete":
            sid = request.form.get("sid")
            conn.execute("DELETE FROM students WHERE id=?", (sid,))
            conn.commit()
            load_known_faces()
            flash("Student deleted.", "info")

        elif action == "encode":
            # Re-encode from existing photo
            sid = request.form.get("sid")
            s   = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
            if s and s["photo_path"]:
                fpath = os.path.join(STUDENT_IMAGES_DIR, s["photo_path"])
                enc   = encode_student_image(fpath)
                if enc:
                    conn.execute("UPDATE students SET encoding_blob=? WHERE id=?",
                                 (pickle.dumps(enc), sid))
                    conn.commit()
                    load_known_faces()
                    flash("Face re-encoded successfully.", "success")
                else:
                    flash("No face detected in saved photo.", "warning")

    students = conn.execute(
        "SELECT * FROM students ORDER BY roll_no"
    ).fetchall()
    conn.close()
    return render_template("add_student.html", students=students)


@app.route("/admin/reports")
@login_required
@roles("super_admin")
def all_reports():
    conn = get_db()
    lectures = conn.execute("""
        SELECT l.*, u.name as fname,
               COUNT(a.id) as total,
               SUM(CASE WHEN a.final_status='Present' THEN 1 ELSE 0 END) as present,
               SUM(CASE WHEN a.final_status='Absent'  THEN 1 ELSE 0 END) as absent
        FROM lectures l
        JOIN users u ON l.faculty_id=u.id
        LEFT JOIN attendance a ON l.id=a.lecture_id
        GROUP BY l.id
        ORDER BY l.date DESC, l.start_time DESC
        LIMIT 60
    """).fetchall()
    conn.close()
    return render_template("all_reports.html", lectures=lectures)


@app.route("/admin/analytics")
@login_required
@roles("super_admin")
def admin_analytics():
    conn  = get_db()
    names = [r["name"] for r in conn.execute("SELECT name FROM students").fetchall()]
    conn.close()
    data  = sorted([get_student_analytics(n) for n in names],
                   key=lambda x: x["percentage"])
    return render_template("analytics.html", data=data,
                           subject="All Subjects",
                           back_url=url_for("admin_dashboard"))


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTES — FACULTY
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/faculty/dashboard")
@login_required
@roles("faculty","super_admin")
def faculty_dashboard():
    fid  = session["uid"]
    conn = get_db()

    lectures = conn.execute("""
        SELECT l.*,
               COUNT(a.id) as total,
               SUM(CASE WHEN a.final_status='Present' THEN 1 ELSE 0 END)    as present,
               SUM(CASE WHEN a.final_status='Late'    THEN 1 ELSE 0 END)    as late,
               SUM(CASE WHEN a.final_status='Early Exit' THEN 1 ELSE 0 END) as early,
               SUM(CASE WHEN a.final_status='Absent'  THEN 1 ELSE 0 END)    as absent
        FROM lectures l
        LEFT JOIN attendance a ON l.id=a.lecture_id
        WHERE l.faculty_id=?
        GROUP BY l.id
        ORDER BY l.date DESC, l.start_time DESC
        LIMIT 12
    """, (fid,)).fetchall()

    today_name = datetime.now().strftime("%A")
    timetable  = conn.execute(
        "SELECT * FROM timetable WHERE faculty_id=? AND day_of_week=?",
        (fid, today_name)
    ).fetchall()

    # Stats totals
    stats = conn.execute("""
        SELECT COUNT(DISTINCT l.id) as lec_cnt,
               COUNT(a.id) as att_cnt,
               SUM(CASE WHEN a.final_status='Present' THEN 1 ELSE 0 END) as present_cnt
        FROM lectures l
        LEFT JOIN attendance a ON l.id=a.lecture_id
        WHERE l.faculty_id=?
    """, (fid,)).fetchone()

    # Active lecture for this faculty
    active = next((ls.to_dict() for ls in active_lectures.values()
                   if ls.faculty_id == fid), None)

    conn.close()
    return render_template("faculty_dashboard.html",
        lectures=lectures, timetable=timetable,
        stats=stats, active=active)


@app.route("/faculty/start_lecture", methods=["GET","POST"])
@login_required
@roles("faculty","super_admin")
def start_lecture():
    fid = session["uid"]

    # If already active, redirect to monitor
    for lid, ls in active_lectures.items():
        if ls.faculty_id == fid:
            return redirect(url_for("lecture_monitor", lid=lid))

    conn = get_db()
    subjects = [r["subject"] for r in conn.execute(
        "SELECT DISTINCT subject FROM timetable WHERE faculty_id=?", (fid,)
    ).fetchall()]
    if not subjects:
        subjects = [session.get("subject","General")]
    conn.close()

    if request.method == "POST":
        subject = request.form.get("subject", subjects[0])
        room    = request.form.get("room","Lab-1")
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO lectures (faculty_id,subject,date,start_time,room,status)
            VALUES (?,?,?,?,?,'active')
        """, (fid, subject, date.today().isoformat(),
              datetime.now().strftime("%H:%M"), room))
        lid = cur.lastrowid
        conn.commit();  conn.close()

        with _lock:
            active_lectures[lid] = LectureSession(lid, subject, fid)

        return redirect(url_for("lecture_monitor", lid=lid))

    return render_template("start_lecture.html", subjects=subjects)


@app.route("/faculty/lecture/<int:lid>/monitor")
@login_required
@roles("faculty","super_admin")
def lecture_monitor(lid: int):
    ls = active_lectures.get(lid)
    if not ls:
        flash("Lecture not found or already completed.", "warning")
        return redirect(url_for("faculty_dashboard"))
    return render_template("lecture_monitor.html",
        ls=ls.to_dict(), lid=lid, schedule=CAPTURE_SCHEDULE)


@app.route("/faculty/attendance/<int:lid>")
@login_required
@roles("faculty","super_admin")
def attendance_report(lid: int):
    summary = get_lecture_summary(lid)
    return render_template("attendance_report.html", **summary)


@app.route("/faculty/analytics")
@login_required
@roles("faculty","super_admin")
def faculty_analytics():
    subject = session.get("subject","")
    conn    = get_db()
    names   = [r["name"] for r in conn.execute("SELECT name FROM students").fetchall()]
    conn.close()
    data    = sorted([get_student_analytics(n, subject) for n in names],
                     key=lambda x: x["percentage"])
    return render_template("analytics.html", data=data,
                           subject=subject,
                           back_url=url_for("faculty_dashboard"))


# ═════════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/api/lecture/<int:lid>/status")
@login_required
def api_lecture_status(lid: int):
    ls = active_lectures.get(lid)
    return jsonify(ls.to_dict() if ls else {"status":"not_found"})


@app.route("/api/lecture/<int:lid>/capture", methods=["POST"])
@login_required
def api_capture(lid: int):
    """Receive base64 frame from browser, run recognition, save result."""
    ls = active_lectures.get(lid)
    if not ls:
        return jsonify({"error":"Lecture not active"}), 404

    payload     = request.get_json(force=True) or {}
    cap_num     = int(payload.get("cap_num", 1))
    image_b64   = payload.get("image","")

    if cap_num in ls.captures:
        return jsonify({"error":"Already captured"}), 400

    try:
        raw   = base64.b64decode(image_b64.split(",")[-1])
        arr   = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # Spoof check
        with ls._lock:
            spoof = detect_spoof(ls.prev_frame, frame)
            ls.prev_frame = frame.copy()

        # Face recognition
        names, annotated = recognize_faces(frame)

        # Save annotated image
        fname = f"lec{lid}_cap{cap_num}_{int(time.time())}.jpg"
        fpath = os.path.join(CAPTURED_DIR, fname)
        cv2.imwrite(fpath, annotated)

        with ls._lock:
            ls.captures[cap_num] = {
                "names": names,
                "path":  f"captured_images/{fname}",
                "spoof": spoof,
            }
            if spoof:
                ls.spoof_set.update(names)
            if ls.is_complete():
                ls.status = "complete"

        # Auto-finalise when all 3 done
        if ls.is_complete():
            threading.Thread(target=_finalise, args=(lid,), daemon=True).start()

        return jsonify({
            "ok": True, "cap_num": cap_num,
            "names": names, "spoof": spoof,
            "path":  f"captured_images/{fname}",
            "complete": ls.is_complete(),
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _finalise(lid: int):
    ls = active_lectures.get(lid)
    if ls:
        compute_attendance(ls)
        with _lock:
            active_lectures.pop(lid, None)


@app.route("/api/reload_faces", methods=["POST"])
@login_required
@roles("super_admin")
def api_reload_faces():
    load_known_faces()
    return jsonify({"ok": True, "count": len(known_names)})


@app.route("/api/analytics/<string:name>")
@login_required
def api_analytics(name: str):
    return jsonify(get_student_analytics(name))


# ─── Webcam stream (server-side, optional) ────────────────────────────────

def _gen_frames():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            _, buf = cv2.imencode(".jpg", frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + buf.tobytes() + b"\r\n")
            time.sleep(0.04)
    finally:
        cap.release()


@app.route("/api/video_feed")
@login_required
def video_feed():
    return Response(_gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    load_known_faces()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)

# ── Context processor — inject 'now' into all templates ──────────────────
@app.context_processor
def inject_now():
    return {"now": datetime.now()}
