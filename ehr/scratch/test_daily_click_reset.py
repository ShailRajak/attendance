import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data
from attendance.services.analytics_service import get_overtime_dashboard_data

cache.clear()
admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("1. SIMULATING CLICKING 'WEEKLY'")
print("============================================================")
weekly_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "weekly"})
print("Period:", weekly_ctx.get("period"))
print("Start Date:", weekly_ctx.get("start_date"), "End Date:", weekly_ctx.get("end_date"))

print("\n============================================================")
print("2. SIMULATING CLICKING 'CUSTOM RANGE' (2026-07-10 to 2026-07-15)")
print("============================================================")
custom_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "custom", "custom_start": "2026-07-10", "custom_end": "2026-07-15"})
print("Period:", custom_ctx.get("period"))
print("Start Date:", custom_ctx.get("start_date"), "End Date:", custom_ctx.get("end_date"))

print("\n============================================================")
print("3. SIMULATING CLICKING 'DAILY' AGAIN (with leftover custom query params)")
print("============================================================")
daily_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "daily", "custom_start": "2026-07-10", "custom_end": "2026-07-15"})
print("Period:", daily_ctx.get("period"))
print("Start Date:", daily_ctx.get("start_date"), "End Date:", daily_ctx.get("end_date"))
assert daily_ctx.get("period") == "daily", "FAILED: Daily click did not reset to daily!"
assert daily_ctx.get("start_date") != "2026-07-10", "FAILED: Daily click still used custom start date!"

print("\n============================================================")
print("4. OVERTIME DASHBOARD DAILY CLICK RESET TEST")
print("============================================================")
ot_daily_ctx = get_overtime_dashboard_data(admin_user, get_params={"period": "daily", "custom_start": "2026-07-10", "custom_end": "2026-07-15"})
print("OT Period:", ot_daily_ctx.get("period"))
print("OT Start Date:", ot_daily_ctx.get("start_date"), "OT End Date:", ot_daily_ctx.get("end_date"))
assert ot_daily_ctx.get("period") == "daily", "FAILED: OT Daily click did not reset to daily!"

print("\nALL TESTS PASSED SUCCESSFULLY! Clicking Daily cleanly resets to standard Daily view!")
