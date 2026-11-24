# Student Attendance System (Flask) - Option A (File-based + QR + Excel export)
## Features
- Admin login (default admin/password)
- Add / Edit / Delete students
- Mark attendance (daily)
- QR scanner to toggle presence (student QR should be student ID)
- Export attendance to Excel
- File-based storage (data/*.json) — easy to move / backup

## Run locally
1. Create and activate a Python virtualenv
2. Install requirements: `pip install -r requirements.txt`
3. Run: `python app.py`
4. Open: http://127.0.0.1:5000/login
