from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from attendance import AttendanceSystem
from werkzeug.security import check_password_hash, generate_password_hash
import io
import json

app = Flask(__name__)
app.secret_key = 'change_this_secret'  # change before deploying
system = AttendanceSystem()

# simple admin credentials stored in file by AttendanceSystem (hashed)
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ok = system.verify_admin(username, password)
        if ok:
            session['user'] = username
            return redirect(url_for('dashboard'))
        flash('Invalid credentials','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **k):
        if 'user' not in session:
            return redirect(url_for('login'))
        return fn(*a, **k)
    return wrapper

@app.route('/')
@login_required
def dashboard():
    students = system.get_students()
    percentages = system.get_attendance_percentage()
    today = system.get_today_str()
    todays_attendance = system.get_attendance_for_date(today)
    return render_template('index.html', students=students, percentages=percentages, today=today, todays_attendance=todays_attendance, system=system)

@app.route('/students')
@login_required
def students():
    students = system.get_students()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['GET','POST'])
@login_required
def add_student():
    if request.method == 'POST':
        name = request.form['name'].strip()
        system.add_student(name)
        return redirect(url_for('students'))
    return render_template('add_student.html')

@app.route('/students/edit/<student_id>', methods=['GET','POST'])
@login_required
def edit_student(student_id):
    student = system.get_student_by_id(student_id)
    if not student:
        return redirect(url_for('students'))
    if request.method == 'POST':
        newname = request.form['name'].strip()
        system.edit_student(student_id, newname)
        return redirect(url_for('students'))
    return render_template('edit_student.html', student=student)

@app.route('/students/delete/<student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    system.delete_student(student_id)
    return redirect(url_for('students'))

@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance():
    students = system.get_students()
    if request.method == 'POST':
        present = request.form.getlist('present')
        # present contains student ids
        system.mark_attendance_for_today(present)
        flash('Attendance saved for today','success')
        return redirect(url_for('dashboard'))
    return render_template('attendance.html', students=students)

@app.route('/attendance/history')
@login_required
def attendance_history():
    history = system.get_all_attendance()
    students = system.get_students()
    return render_template('attendance_history.html', history=history, students=students)

@app.route('/export')
@login_required
def export():
    # export to excel and send file
    buf = system.export_excel_bytes()
    return send_file(buf, download_name='attendance_export.xlsx', as_attachment=True)

@app.route('/qr')
@login_required
def qr():
    # page that contains the QR scanner to mark attendance
    students = system.get_students()
    return render_template('qr.html', students=students)

# QR toggle endpoint
@app.route('/qr_toggle', methods=['POST'])
@login_required
def qr_toggle():
    data = request.get_json()
    sid = data.get('id')
    # toggle presence for today
    today = system.get_today_str()
    attendance = system.get_all_attendance()
    # ensure date exists
    if today not in attendance:
        attendance[today] = {}
    current = attendance[today].get(sid, False)
    attendance[today][sid] = not current
    # write back
    with open(system.attendance_file, 'w') as fh:
        json.dump(attendance, fh, indent=2)
    return {'ok': True, 'message': f'Toggled {sid} -> {not current}'}

# expose system to templates (so templates can call system.get_student_by_id)
@app.context_processor
def inject_system():
    return dict(system=system)

if __name__ == '__main__':
    app.run(debug=True)
