import os, json, hashlib, datetime, uuid, io
import pandas as pd

class AttendanceSystem:
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.students_file = os.path.join(self.data_dir, 'students.json')
        self.attendance_file = os.path.join(self.data_dir, 'attendance.json')
        self.admin_file = os.path.join(self.data_dir, 'admin.json')
        for f in (self.students_file, self.attendance_file, self.admin_file):
            if not os.path.exists(f):
                with open(f,'w') as fh:
                    if f==self.admin_file:
                        # default admin: admin / password -> change later
                        default = {'username':'admin','password_hash': self._hash('password')}
                        json.dump(default, fh)
                    else:
                        json.dump([], fh)

    def _hash(self, password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def verify_admin(self, username, password):
        with open(self.admin_file,'r') as f:
            data = json.load(f)
        return username==data.get('username') and self._hash(password)==data.get('password_hash')

    def set_admin(self, username, password):
        with open(self.admin_file,'w') as f:
            json.dump({'username':username,'password_hash': self._hash(password)}, f)

    # Students are stored as list of {"id":..., "name":...}
    def add_student(self, name):
        students = self.get_students(raw=True)
        new = {'id': str(uuid.uuid4()), 'name': name}
        students.append(new)
        with open(self.students_file,'w') as f:
            json.dump(students, f, indent=2)

    def get_students(self, raw=False):
        with open(self.students_file,'r') as f:
            data = json.load(f)
        return data if raw else [s for s in data]

    def get_student_by_id(self, student_id):
        students = self.get_students(raw=True)
        for s in students:
            if s['id']==student_id:
                return s
        return None

    def edit_student(self, student_id, newname):
        students = self.get_students(raw=True)
        for s in students:
            if s['id']==student_id:
                s['name'] = newname
        with open(self.students_file,'w') as f:
            json.dump(students, f, indent=2)

    def delete_student(self, student_id):
        students = self.get_students(raw=True)
        students = [s for s in students if s['id']!=student_id]
        with open(self.students_file,'w') as f:
            json.dump(students, f, indent=2)
        # also remove attendance records for this student
        attendance = self._read_attendance()
        for date, rec in attendance.items():
            if student_id in rec:
                rec.pop(student_id, None)
        self._write_attendance(attendance)

    def _read_attendance(self):
        with open(self.attendance_file,'r') as f:
            data = json.load(f)
        return data

    def _write_attendance(self, data):
        with open(self.attendance_file,'w') as f:
            json.dump(data, f, indent=2)

    def get_today_str(self):
        return datetime.date.today().isoformat()

    def mark_attendance_for_today(self, present_ids):
        attendance = self._read_attendance()
        today = self.get_today_str()
        if today not in attendance:
            attendance[today] = {}
        students = self.get_students(raw=True)
        for s in students:
            attendance[today][s['id']] = (s['id'] in present_ids)
        self._write_attendance(attendance)

    def get_attendance_for_date(self, date_str):
        attendance = self._read_attendance()
        return attendance.get(date_str, {})

    def get_all_attendance(self):
        return self._read_attendance()

    def get_attendance_percentage(self):
        attendance = self._read_attendance()
        students = self.get_students(raw=True)
        totals = {s['id']:{'name':s['name'],'P':0,'T':0} for s in students}
        for date, rec in attendance.items():
            for sid, present in rec.items():
                if sid not in totals:
                    # student removed, skip
                    continue
                totals[sid]['T'] += 1
                if present:
                    totals[sid]['P'] += 1
        percent = {}
        for sid, r in totals.items():
            if r['T']==0:
                percent[r['name']] = 0.0
            else:
                percent[r['name']] = round((r['P']/r['T'])*100,2)
        return percent

    def export_excel_bytes(self):
        attendance = self._read_attendance()
        students = self.get_students(raw=True)
        sid_to_name = {s['id']:s['name'] for s in students}
        # build DataFrame with rows per date, columns per student (Present/Absent)
        rows = []
        for date, rec in attendance.items():
            row = {'Date': date}
            for sid, name in sid_to_name.items():
                val = rec.get(sid, False)
                row[name] = 'Present' if val else 'Absent'
            rows.append(row)
        if not rows:
            df = pd.DataFrame(columns=['Date'] + list(sid_to_name.values()))
        else:
            df = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')
        buf.seek(0)
        return buf
