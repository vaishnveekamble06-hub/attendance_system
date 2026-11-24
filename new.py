# app.py
import os, json, uuid, io, datetime
from functools import wraps
from flask import (
    Flask, request, redirect, session, send_file,
    render_template_string, url_for, flash
)

# External libs: pandas, qrcode, PIL
# Install: pip install flask pandas openpyxl qrcode pillow
import pandas as pd
import qrcode
from PIL import Image

app = Flask(__name__)
app.secret_key = "change_me_to_a_random_secret!"

# Data files (will be created automatically)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
ATT_FILE = os.path.join(DATA_DIR, "attendance.json")
ADMIN_FILE = os.path.join(DATA_DIR, "admin.json")

def ensure_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, "w") as f:
            json.dump([], f)
    if not os.path.exists(ATT_FILE):
        with open(ATT_FILE, "w") as f:
            json.dump({}, f)
    if not os.path.exists(ADMIN_FILE):
        # default admin credentials (change after first login)
        with open(ADMIN_FILE, "w") as f:
            json.dump({"username": "admin", "password": "password"}, f)

ensure_data()

# -----------------------
# Helper functions
# -----------------------
def load_students():
    with open(STUDENTS_FILE, "r") as f:
        return json.load(f)

def save_students(students):
    with open(STUDENTS_FILE, "w") as f:
        json.dump(students, f, indent=2)

def load_attendance():
    with open(ATT_FILE, "r") as f:
        return json.load(f)

def save_attendance(att):
    with open(ATT_FILE, "w") as f:
        json.dump(att, f, indent=2)

def load_admin():
    with open(ADMIN_FILE, "r") as f:
        return json.load(f)

def save_admin(admin):
    with open(ADMIN_FILE, "w") as f:
        json.dump(admin, f, indent=2)

def find_student_by_id(sid):
    students = load_students()
    for s in students:
        if s["id"] == sid:
            return s
    return None

def find_student_by_urn(urn):
    students = load_students()
    for s in students:
        if s["urn"] == urn:
            return s
    return None

def today_str():
    return datetime.date.today().isoformat()

def attendance_percentages():
    att = load_attendance()
    students = load_students()
    id_to_name = {s["id"]: s["name"] for s in students}
    totals = {s["id"]: {"P":0,"T":0,"name":s["name"], "urn": s["urn"]} for s in students}
    for date, rec in att.items():
        for sid, present in rec.items():
            if sid not in totals:
                continue
            totals[sid]["T"] += 1
            if present:
                totals[sid]["P"] += 1
    out = {}
    for sid, r in totals.items():
        pct = round((r["P"] / r["T"]) * 100, 2) if r["T"]>0 else 0.0
        out[sid] = {"name": r["name"], "urn": r["urn"], "pct": pct, "present": r["P"], "total": r["T"]}
    return out

# -----------------------
# Auth decorator
# -----------------------
def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*a, **k)
    return wrapper

# -----------------------
# Routes
# -----------------------

# Embedded templates use Bootstrap 5 and a bit of custom CSS
BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Student Attendance System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      body{{background:#f5f8fb}}
      .nav-brand{{font-weight:700;letter-spacing:0.4px}}
      .card-compact{{border-radius:12px;box-shadow:0 6px 18px rgba(23,23,23,0.07)}}
      .qr-thumb{{width:96px;height:96px;object-fit:contain;border-radius:8px;border:1px solid #e6e9ef}}
      .small-muted{{font-size:0.9rem;color:#6c757d}}
      footer{{margin-top:36px;text-align:center;color:#6c757d;font-size:0.9rem}}
      .action-row a, .action-row form{{display:inline-block;margin-right:8px}}
    </style>
  </head>
  <body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
      <div class="container">
        <a class="navbar-brand nav-brand" href="{{ url_for('home') }}">Attendance</a>
        <div class="collapse navbar-collapse">
          <ul class="navbar-nav ms-auto">
            {% if session.get('logged_in') %}
            <li class="nav-item"><a class="nav-link" href="{{ url_for('home') }}">Dashboard</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('students') }}">Students</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('attendance') }}">Mark Attendance</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('history') }}">History</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('qr_scan') }}">QR Scan</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('export_xlsx') }}">Export</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('settings') }}">Settings</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('logout') }}">Logout</a></li>
            {% endif %}
          </ul>
        </div>
      </div>
    </nav>

    <div class="container py-4">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          <div class="mb-3">
            {% for m in messages %}
              <div class="alert alert-info">{{ m }}</div>
            {% endfor %}
          </div>
        {% endif %}
      {% endwith %}
      {{ body }}
    </div>

    <footer>
      Built with ❤️ — Single-file Flask app — Data stored in <code>data/</code>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""

# -----------------------
# Login
# -----------------------
@app.route("/", methods=["GET","POST"])
def login():
    admin = load_admin()
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if u == admin.get("username") and p == admin.get("password"):
            session["logged_in"] = True
            flash("Welcome, " + u)
            return redirect(url_for("home"))
        flash("Invalid credentials")
    body = render_template_string("""
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card card-compact p-4">
          <h4 class="mb-3">Admin Login</h4>
          <form method="post">
            <div class="mb-3"><input class="form-control" name="username" placeholder="Username" required></div>
            <div class="mb-3"><input class="form-control" name="password" placeholder="Password" type="password" required></div>
            <div class="d-flex justify-content-between align-items-center">
              <button class="btn btn-primary">Login</button>
              <small class="small-muted">Default: admin / password</small>
            </div>
          </form>
        </div>
      </div>
    </div>
    """)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    flash("Logged out")
    return redirect(url_for("login"))

# -----------------------
# Settings (change admin creds)
# -----------------------
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    admin = load_admin()
    if request.method == "POST":
        newu = request.form.get("username").strip()
        newp = request.form.get("password").strip()
        if newu and newp:
            save_admin({"username": newu, "password": newp})
            flash("Admin credentials updated. Please login again.")
            session.pop("logged_in", None)
            return redirect(url_for("login"))
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h4>Admin Settings</h4>
        <form method="post">
          <div class="mb-3"><label class="form-label">Username</label><input class="form-control" name="username" value="{{admin.username}}" required></div>
          <div class="mb-3"><label class="form-label">Password</label><input class="form-control" name="password" value="{{admin.password}}" required></div>
          <button class="btn btn-warning">Save (will log you out)</button>
        </form>
      </div>
    """, admin=admin)
    return render_template_string(BASE_TEMPLATE, body=body)

# -----------------------
# Home / Dashboard
# -----------------------
@app.route("/home")
@login_required
def home():
    students = load_students()
    perc = attendance_percentages()
    today = today_str()
    att = load_attendance().get(today, {})
    # build today's quick list (name, urn, present)
    today_list = []
    for s in students:
        present = att.get(s["id"], False)
        today_list.append({"name": s["name"], "urn": s["urn"], "present": present, "id": s["id"]})
    body = render_template_string("""
      <div class="row">
        <div class="col-md-7">
          <div class="card card-compact p-3 mb-3">
            <h5>Today's Attendance — {{today}}</h5>
            <a class="btn btn-sm btn-primary mb-2" href="{{ url_for('attendance') }}">Mark / Edit Today's Attendance</a>
            <ul class="list-group">
              {% for t in today_list %}
                <li class="list-group-item d-flex justify-content-between align-items-center">
                  <div>
                    <strong>{{ t.name }}</strong><br><small class="small-muted">URN: {{ t.urn }}</small>
                  </div>
                  <div>
                    {% if t.present %}
                      <span class="badge bg-success">Present</span>
                    {% else %}
                      <span class="badge bg-secondary">Absent</span>
                    {% endif %}
                  </div>
                </li>
              {% endfor %}
            </ul>
          </div>
          <div class="card card-compact p-3">
            <h5>Attendance History (recent 10)</h5>
            {% for date, rec in history.items()|reverse %}
              <div class="mb-2">
                <strong>{{ date }}</strong> — Present: {{ rec|selectattr('1')|list|length }} / {{ rec|length }}
              </div>
            {% endfor %}
            <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('history') }}">View full history</a>
          </div>
        </div>

        <div class="col-md-5">
          <div class="card card-compact p-3">
            <h5>Attendance Percentage</h5>
            <table class="table table-sm">
              <thead><tr><th>Name</th><th>URN</th><th>%</th></tr></thead>
              <tbody>
                {% for sid,data in percentages.items() %}
                  <tr>
                    <td>{{ data.name }}</td>
                    <td>{{ data.urn }}</td>
                    <td>{{ data.pct }}%</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
            <a class="btn btn-success btn-sm" href="{{ url_for('export_xlsx') }}">Export Excel</a>
          </div>
          <div class="card card-compact p-3 mt-3 text-center">
            <h6>Quick Actions</h6>
            <a class="btn btn-outline-primary btn-sm me-2" href="{{ url_for('students') }}">Manage Students</a>
            <a class="btn btn-outline-primary btn-sm" href="{{ url_for('qr_scan') }}">Open QR Scanner</a>
          </div>
        </div>
      </div>
    """, today=today, today_list=today_list, percentages=perc, history=get_recent_history(10))
    return render_template_string(BASE_TEMPLATE, body=body)

# small helper to present history counts conveniently
def get_recent_history(n=10):
    att = load_attendance()
    items = list(att.items())
    items.sort(reverse=True)
    recent = dict(items[:n])
    # convert rec to dict of sid->present for template convenience
    out = {}
    for date, rec in recent.items():
        out[date] = rec
    return out

# -----------------------
# Students CRUD
# -----------------------
@app.route("/students")
@login_required
def students():
    students = load_students()
    # attach QR url
    for s in students:
        s["qr_url"] = url_for("qr_code", urn=s["urn"])
    body = render_template_string("""
      <div class="card card-compact p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5>Students ({{ students|length }})</h5>
          <div>
            <a class="btn btn-primary btn-sm" href="{{ url_for('add_student') }}">Add Student</a>
          </div>
        </div>
        <table class="table">
          <thead><tr><th>Name</th><th>URN</th><th>QR</th><th>Actions</th></tr></thead>
          <tbody>
            {% for s in students %}
              <tr>
                <td>{{ s.name }}</td>
                <td>{{ s.urn }}</td>
                <td><img src="{{ s.qr_url }}" class="qr-thumb"></td>
                <td class="action-row">
                  <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('edit_student', sid=s.id) }}">Edit</a>
                  <a class="btn btn-sm btn-outline-danger" href="{{ url_for('delete_student', sid=s.id) }}" onclick="return confirm('Delete this student?')">Delete</a>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    """, students=students)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/students/add", methods=["GET","POST"])
@login_required
def add_student():
    if request.method == "POST":
        name = request.form.get("name").strip()
        urn = request.form.get("urn").strip()
        if not name or not urn:
            flash("Name and URN required")
            return redirect(url_for("add_student"))
        students = load_students()
        # ensure URN unique
        if any(s["urn"]==urn for s in students):
            flash("URN already exists")
            return redirect(url_for("add_student"))
        sid = str(uuid.uuid4())
        students.append({"id": sid, "name": name, "urn": urn})
        save_students(students)
        flash("Student added")
        return redirect(url_for("students"))
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h5>Add Student</h5>
        <form method="post">
          <div class="mb-2"><input class="form-control" name="name" placeholder="Full name" required></div>
          <div class="mb-2"><input class="form-control" name="urn" placeholder="URN (unique)" required></div>
          <button class="btn btn-success">Add</button>
        </form>
      </div>
    """)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/students/edit/<sid>", methods=["GET","POST"])
@login_required
def edit_student(sid):
    students = load_students()
    s = find_student_by_id(sid)
    if not s:
        flash("Student not found")
        return redirect(url_for("students"))
    if request.method == "POST":
        new_name = request.form.get("name").strip()
        new_urn = request.form.get("urn").strip()
        # check URN uniqueness (except this student)
        if any(x["urn"]==new_urn and x["id"]!=sid for x in students):
            flash("URN already used by another student")
            return redirect(url_for("edit_student", sid=sid))
        for x in students:
            if x["id"]==sid:
                x["name"] = new_name
                x["urn"] = new_urn
        save_students(students)
        flash("Student updated")
        return redirect(url_for("students"))
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h5>Edit Student</h5>
        <form method="post">
          <div class="mb-2"><input class="form-control" name="name" value="{{ s.name }}" required></div>
          <div class="mb-2"><input class="form-control" name="urn" value="{{ s.urn }}" required></div>
          <button class="btn btn-primary">Save</button>
        </form>
      </div>
    """, s=s)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/students/delete/<sid>")
@login_required
def delete_student(sid):
    students = load_students()
    students = [s for s in students if s["id"]!=sid]
    save_students(students)
    # also remove attendance entries for this student
    att = load_attendance()
    for date in list(att.keys()):
        if sid in att[date]:
            att[date].pop(sid, None)
    save_attendance(att)
    flash("Student deleted")
    return redirect(url_for("students"))

# -----------------------
# Attendance mark and history
# -----------------------
@app.route("/attendance", methods=["GET","POST"])
@login_required
def attendance():
    students = load_students()
    today = today_str()
    att = load_attendance()
    todays = att.get(today, {})
    if request.method == "POST":
        present_ids = request.form.getlist("present")
        # build today's dict: for each student id -> bool
        rec = {}
        for s in students:
            rec[s["id"]] = (s["id"] in present_ids)
        att[today] = rec
        save_attendance(att)
        flash("Attendance saved for " + today)
        return redirect(url_for("home"))
    # GET: show checkboxes (checked if present)
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h5>Mark Attendance — {{ today }}</h5>
        <form method="post">
          <div class="mb-3">
            {% for s in students %}
              <div class="form-check">
                <input class="form-check-input" type="checkbox" name="present" value="{{ s.id }}" id="c{{ s.id }}" {% if todays.get(s.id) %}checked{% endif %}>
                <label class="form-check-label" for="c{{ s.id }}">{{ s.name }} — <small class="text-muted">URN: {{ s.urn }}</small></label>
              </div>
            {% endfor %}
          </div>
          <button class="btn btn-success">Save Today's Attendance</button>
        </form>
      </div>
    """, students=students, today=today, todays=todays)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/history")
@login_required
def history():
    att = load_attendance()
    # sort dates desc
    items = sorted(att.items(), reverse=True)
    # for display attach names
    students = {s["id"]: s for s in load_students()}
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h5>Attendance History</h5>
        {% for date, rec in items %}
          <div class="mb-3">
            <strong>{{ date }}</strong>
            <table class="table table-sm mt-2">
              <thead><tr><th>Name</th><th>URN</th><th>Status</th></tr></thead>
              <tbody>
                {% for sid, present in rec.items() %}
                  <tr>
                    <td>{{ students.get(sid).name if students.get(sid) else sid }}</td>
                    <td>{{ students.get(sid).urn if students.get(sid) else '' }}</td>
                    <td>{{ 'Present' if present else 'Absent' }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        {% endfor %}
      </div>
    """, items=items, students=students)
    return render_template_string(BASE_TEMPLATE, body=body)

# -----------------------
# Export to Excel
# -----------------------
@app.route("/export")
@login_required
def export_xlsx():
    att = load_attendance()
    students = load_students()
    sid_to_name = {s["id"]: s["name"] for s in students}
    sid_to_urn = {s["id"]: s["urn"] for s in students}
    rows = []
    for date, rec in sorted(att.items()):
        for sid, present in rec.items():
            rows.append({"Date": date, "Name": sid_to_name.get(sid, sid), "URN": sid_to_urn.get(sid, ""), "Status": "Present" if present else "Absent"})
    if not rows:
        df = pd.DataFrame(columns=["Date","Name","URN","Status"])
    else:
        df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    buf.seek(0)
    return send_file(buf, download_name="attendance.xlsx", as_attachment=True)

# -----------------------
# QR: generate image & scanner
# -----------------------
@app.route("/qr_code/<urn>")
@login_required
def qr_code(urn):
    # generate QR for URN on the fly
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(urn)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/qr-scan")
@login_required
def qr_scan():
    # page with html5-qrcode scanner that POSTs to /qr_toggle
    body = render_template_string("""
      <div class="card card-compact p-3">
        <h5>QR Scanner</h5>
        <p>Scan student's URN QR. Scanning toggles presence for today.</p>
        <div id="reader" style="width:100%"></div>
        <div class="mt-2" id="status"></div>
      </div>

      <script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
      <script>
        const reader = new Html5Qrcode("reader");
        function onSuccess(decodedText, decodedResult) {
          fetch("{{ url_for('qr_toggle') }}", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({urn: decodedText})
          }).then(r=>r.json()).then(j=>{
            document.getElementById("status").innerText = j.message;
          });
        }
        Html5Qrcode.getCameras().then(devices=>{
          if (devices && devices.length) {
            reader.start({ facingMode: "environment" }, { fps: 10 }, onSuccess);
          } else {
            document.getElementById("status").innerText = "No camera found";
          }
        }).catch(err=>{
          document.getElementById("status").innerText = "Camera error: "+err;
        });
      </script>
    """)
    return render_template_string(BASE_TEMPLATE, body=body)

@app.route("/qr_toggle", methods=["POST"])
@login_required
def qr_toggle():
    data = request.get_json() or {}
    urn = data.get("urn")
    if not urn:
        return {"ok": False, "message": "No URN received"}
    student = find_student_by_urn(urn)
    if not student:
        return {"ok": False, "message": f"No student with URN {urn}"}
    sid = student["id"]
    att = load_attendance()
    today = today_str()
    if today not in att:
        att[today] = {}
    current = att[today].get(sid, False)
    att[today][sid] = not current
    save_attendance(att)
    return {"ok": True, "message": f"{student['name']} -> {'Present' if not current else 'Absent'}"}

# -----------------------
# Run the app
# -----------------------
if __name__ == "__main__":
    # create data on first run
    ensure_data()
    print("Data directory:", DATA_DIR)
    print("Default admin credentials: admin / password  (change on Settings after login)")
    app.run(debug=True, port=5000)
