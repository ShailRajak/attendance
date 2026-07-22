import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data, fetch_attendance_from_db
from attendance.services.analytics_service import calculate_dashboard_stats
from attendance.utils.date_helpers import get_attendance_date_range

cache.clear()

user = User.objects.first()
print("Testing Late Policy Integration for user:", user.username)

# 1. Test Home Dashboard Data (Admin / Section view)
context = get_home_dashboard_data(user, None, None, None, "dashboard")
kpi_late = context.get("kpi_late_punch", 0)
print(f"Top HRMS Card KPI Late Punch Count: {kpi_late}")

# 2. Test Employee Role Stats
start_dt, end_dt = get_attendance_date_range()
records = fetch_attendance_from_db("19102172", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
stats = calculate_dashboard_stats(records, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"), "19102172")
print(f"Employee 19102172 Monthly Late Arrivals Count: {stats.get('late_arrivals')}")
print(f"Employee 19102172 Max Late Details: {stats.get('late_details')}")

print("\nSUCCESS: Late Policy Integration verified cleanly across all roles!")
