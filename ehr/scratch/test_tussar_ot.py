import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data

cache.clear()

user = User.objects.first()
context = get_home_dashboard_data(user, None, None, None, "dashboard")
attendance = context.get("attendance", [])

target_ids = ["19105108", "19105203", "19105326", "19105434", "19105639"]
print("=== VERIFYING ALL EMPLOYEES FROM SCREENSHOT ===")
for r in attendance:
    if r.get("date") == "21/07/2026" and r.get("employee_id") in target_ids:
        print(f"[{r.get('employee_id')}] {r.get('employee_name'):<22} | In: {r.get('in_time'):<5} | Out: {r.get('out_time'):<5} | Work: {r.get('work_hrs'):<5} | OT: {r.get('ot_hrs'):<5} | Status: {r.get('status')}")
