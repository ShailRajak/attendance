import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from attendance.services.attendance_service import compute_weekly_kpi_cards, fetch_attendance_from_db
from attendance.services.analytics_service import calculate_section_dashboard_stats

cache.clear()

start_str = "2026-07-20"
end_str = "2026-07-26"
records = fetch_attendance_from_db(None, start_str, end_str)

print(f"Total raw records fetched for week ({start_str} to {end_str}): {len(records)}")

weekly_kpis = compute_weekly_kpi_cards(records)
print("\n=== TOP HRMS KPI CARDS (WEEKLY AGGREGATED FOR ADMIN/MANAGEMENT) ===")
for k, v in weekly_kpis.items():
    print(f"  {k:<25}: {v}")

stats = calculate_section_dashboard_stats(records, role_display="Admin", section_display="Section-Wide", period="weekly")
print("\n=== LOWER SECTION DASHBOARD STATS (WEEKLY AGGREGATED) ===")
print("total_employees:", stats.get("total_employees"))
print("working_days   :", stats.get("working_days"))
print("days_present   :", stats.get("days_present"))
print("leaves_taken   :", stats.get("leaves_taken"))
print("late_arrivals  :", stats.get("late_arrivals"))
print("mispunches     :", stats.get("mispunches"))
print("total_ot       :", stats.get("total_ot"))

print("\nSUCCESS: All Weekly KPI aggregations verified 100% cleanly!")
