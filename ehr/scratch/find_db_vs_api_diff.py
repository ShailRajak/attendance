import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db
from attendance.models import AttendanceRecord

target_date = "2026-07-21"

api_records = fetch_attendance(employee_id="", start_date=target_date, end_date=target_date)
db_records = fetch_attendance_from_db(employee_id="", start_date=target_date, end_date=target_date)

api_set = set((r.get("Employee ID"), r.get("In Time"), r.get("Out Time")) for r in api_records)
db_set = set((r.get("Employee ID"), r.get("In Time"), r.get("Out Time")) for r in db_records)

db_only = db_set - api_set
api_only = api_set - db_set

print("============================================================")
print(f"RECORDS ONLY IN DB ({len(db_only)} records):")
for r in db_only:
    print(" ", r)

print("============================================================")
print(f"RECORDS ONLY IN API ({len(api_only)} records):")
for r in api_only:
    print(" ", r)
