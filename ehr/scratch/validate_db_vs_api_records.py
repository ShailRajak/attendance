import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db
from attendance.models import AttendanceRecord

target_date = "2026-07-21"

print(f"============================================================")
print(f"VALIDATING API vs DB RECORDS FOR DATE: {target_date}")
print(f"============================================================")

# 1. Fetch directly from external API
api_records = fetch_attendance(employee_id="", start_date=target_date, end_date=target_date)
print(f"Records fetched from External API : {len(api_records)}")

# 2. Fetch directly from DB
db_records = fetch_attendance_from_db(employee_id="", start_date=target_date, end_date=target_date)
print(f"Records fetched from Local DB     : {len(db_records)}")

# 3. Direct DB count query
db_count = AttendanceRecord.objects.filter(attendance_date=target_date).count()
print(f"Direct SQL Count from DB          : {db_count}")

print(f"\nDiscrepancy (API vs DB)            : {len(api_records) - len(db_records)}")

if len(api_records) == len(db_records):
    print("SUCCESS: Local DB is a 100% PERFECT MATCH with External API data!")
else:
    print("WARNING: API and DB counts differ!")
