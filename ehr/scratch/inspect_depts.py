import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()
home_ctx = get_home_dashboard_data(admin_user, "daily", None, None, 2026, None, None, "dashboard")

attendance = home_ctx.get("attendance", [])
print("Total Attendance Rows:", len(attendance))

depts_found = {}
for r in attendance:
    dept = str(r.get("department") or r.get("plant") or r.get("section") or "").strip()
    sec_type = "other"
    dept_lower = dept.lower()
    if '63' in dept_lower or 's63' in dept_lower or 'sector 63' in dept_lower:
        sec_type = "s63"
    elif 'phase 2' in dept_lower or 'c39' in dept_lower or 'c-39' in dept_lower or 'phase-2' in dept_lower:
        sec_type = "c39"
    depts_found[sec_type] = depts_found.get(sec_type, 0) + 1

print("Department Breakdown for Location S63 / C39 / Other:", depts_found)

sample = [(r.get("employee_id"), r.get("department"), r.get("shift_label")) for r in attendance[:10]]
print("Sample rows:", sample)
