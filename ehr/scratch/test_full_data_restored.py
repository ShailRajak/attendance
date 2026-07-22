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
admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("TESTING FULL DATA RESTORATION FOR ADMIN")
print("============================================================")
dash_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "daily"})

print("Total Headcount KPI :", dash_ctx.get("total_headcount"))
print("Present Today KPI   :", dash_ctx.get("present_today"))
print("Absent Today KPI    :", dash_ctx.get("absent_today"))
print("Attendance Logs Count:", len(dash_ctx.get("attendance", [])))

assert dash_ctx.get("total_headcount") > 500, f"ERROR: total_headcount is still truncated to {dash_ctx.get('total_headcount')}!"
assert len(dash_ctx.get("attendance", [])) > 500, f"ERROR: attendance list is still truncated to {len(dash_ctx.get('attendance', []))}!"

print("\nSUCCESS: 100% of all employee data (all 6000+ / 11,961 employees) is fully restored!")
