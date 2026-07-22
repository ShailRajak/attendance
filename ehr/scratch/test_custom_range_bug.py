import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data, fetch_attendance_from_db

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()
print(f"Testing Custom Range for User: {admin_user.username}")

# Simulate GET request with custom_start="2026-07-20" and custom_end="2026-07-20"
get_params = {
    "period": "custom",
    "custom_start": "2026-07-20",
    "custom_end": "2026-07-20",
    "start_date": "2026-07-20",
    "end_date": "2026-07-20",
}

context = get_home_dashboard_data(
    user=admin_user,
    start_date="2026-07-20",
    end_date="2026-07-20",
    query_employee_id=None,
    active_tab="dashboard",
    get_params=get_params,
)

print("\n=== CUSTOM RANGE CONTEXT (2026-07-20 to 2026-07-20) ===")
print("Active Period       :", context.get("period"))
print("Active Start Date   :", context.get("start_date"))
print("Active End Date     :", context.get("end_date"))
print("kpi_total_employees :", context.get("kpi_total_employees"))
print("kpi_present_day     :", context.get("kpi_present_day_shift"))
print("kpi_present_night   :", context.get("kpi_present_night_shift"))
print("kpi_absent          :", context.get("kpi_absent"))

stats = context.get("dashboard_stats", {})
print("\n=== DASHBOARD STATS ===")
print("working_days        :", stats.get("working_days"))
print("days_present        :", stats.get("days_present"))
print("leaves_taken        :", stats.get("leaves_taken"))

# Fetch raw DB records directly for 2026-07-20
raw_recs = fetch_attendance_from_db(None, "2026-07-20", "2026-07-20")
print(f"\nDirect DB fetch for 2026-07-20 returned {len(raw_recs)} records.")
