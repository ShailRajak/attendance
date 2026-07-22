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
print("1. DASHBOARD MONTHLY AGGREGATION TEST FOR ADMIN")
print("============================================================")
dash_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "monthly"})
print("Period Text           :", dash_ctx.get("period_text"))
print("Start Date            :", dash_ctx.get("start_date"))
print("End Date              :", dash_ctx.get("end_date"))
print("kpi_total_employees   :", dash_ctx.get("kpi_total_employees"))
print("kpi_present_day_shift :", dash_ctx.get("kpi_present_day_shift"))
print("kpi_present_night_shift:", dash_ctx.get("kpi_present_night_shift"))
print("kpi_absent            :", dash_ctx.get("kpi_absent"))
print("kpi_on_leave          :", dash_ctx.get("kpi_on_leave"))

dash_stats = dash_ctx.get("dashboard_stats", {})
print("working_days          :", dash_stats.get("working_days"))
print("total_employees       :", dash_stats.get("total_employees"))
print("days_present          :", dash_stats.get("days_present"))

print("\n============================================================")
print("2. OVERTIME DASHBOARD MONTHLY AGGREGATION TEST FOR ADMIN")
print("============================================================")
ot_ctx = get_overtime_dashboard_data(admin_user, get_params={"period": "monthly"})
print("Period Text           :", ot_ctx.get("period_text"))
print("Start Date            :", ot_ctx.get("start_date"))
print("End Date              :", ot_ctx.get("end_date"))
summary_ot = ot_ctx.get("summary", {})
print("Card Punch OT         :", summary_ot.get("card_punch_ot"))
print("Requested OT          :", summary_ot.get("requested_ot"))
print("Weekend OT            :", summary_ot.get("weekend_ot"))
print("Holiday OT            :", summary_ot.get("holiday_ot"))
print("Total OT              :", summary_ot.get("total_ot"))

print("\n============================================================")
print("3. LEAVES DASHBOARD MONTHLY AGGREGATION TEST FOR ADMIN")
print("============================================================")
leaves_ctx = get_leaves_dashboard_data(admin_user, period="monthly", cycle_num=None, week_num=None, year=None, query_employee_id=None)
print("Period Text           :", leaves_ctx.get("period_text"))
print("Start Date            :", leaves_ctx.get("start_str"))
print("End Date              :", leaves_ctx.get("end_str"))
l_stats = leaves_ctx.get("stats", {})
print("Mispunches            :", l_stats.get("mispunch"))
print("Absent/Leaves         :", l_stats.get("leave"))
print("Short Leaves          :", l_stats.get("short_leave"))
print("Half Days             :", l_stats.get("half_day"))
print("Full Days             :", l_stats.get("full_day"))
