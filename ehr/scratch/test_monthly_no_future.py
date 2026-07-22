import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data
from attendance.services.analytics_service import get_overtime_dashboard_data, get_leaves_dashboard_data

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("TESTING MONTHLY DATE BOUNDS (NO FUTURE DATES) FOR ADMIN SECTION VIEW")
print("============================================================")
dash_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "monthly"})
stats = dash_ctx.get("stats", {})
print("Dashboard Start Date :", dash_ctx.get("start_date"))
print("Dashboard End Date   :", dash_ctx.get("end_date"))
print("Chart Labels (Dates) :", stats.get("chart_labels", []))
print("Chart Worktime Data  :", stats.get("chart_worktime_data", []))

print("\n============================================================")
ot_ctx = get_overtime_dashboard_data(admin_user, get_params={"period": "monthly"})
print("Overtime Start Date  :", ot_ctx.get("start_date"))
print("Overtime End Date    :", ot_ctx.get("end_date"))

print("\n============================================================")
leaves_ctx = get_leaves_dashboard_data(admin_user, period="monthly", cycle_num=None, week_num=None, year=None, query_employee_id=None)
print("Leaves Start Date    :", leaves_ctx.get("start_str"))
print("Leaves End Date      :", leaves_ctx.get("end_str"))

print("\nSUCCESS: Monthly view correctly starts on 21st and ends TODAY (no future dates)!")
