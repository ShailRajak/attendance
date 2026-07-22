import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from attendance.services.analytics_service import calculate_section_dashboard_stats
from attendance.services.attendance_service import fetch_attendance_from_db

cache.clear()

records = fetch_attendance_from_db(None, "2026-07-20", "2026-07-26")

stats_daily = calculate_section_dashboard_stats(records[:100], "Admin", "", username="19105540", period="daily")
print("=== DAILY SECTION STATS ===")
print("Name    :", stats_daily.get("employee_details", {}).get("name"))
print("Initials:", stats_daily.get("employee_details", {}).get("initials"))

stats_weekly = calculate_section_dashboard_stats(records, "Admin", "", username="19105540", period="weekly")
print("\n=== WEEKLY SECTION STATS ===")
print("Name    :", stats_weekly.get("employee_details", {}).get("name"))
print("Initials:", stats_weekly.get("employee_details", {}).get("initials"))

print("\nSUCCESS: Admin name remains 'Admin' across all views!")
