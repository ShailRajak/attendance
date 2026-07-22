import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from attendance.services.attendance_service import fetch_attendance_from_db, compute_kpi_cards
from attendance.services.analytics_service import calculate_section_dashboard_stats

cache.clear()

records = fetch_attendance_from_db(None, "2026-07-20", "2026-07-20")
print(f"Total raw records for 2026-07-20: {len(records)}")

kpis_old = compute_kpi_cards(records)
print("\n=== CURRENT TOP KPI CARDS FOR 2026-07-20 ===")
print("kpi_total_employees   :", kpis_old.get("kpi_total_employees"))
print("kpi_total_day_shift   :", kpis_old.get("kpi_total_day_shift"))
print("kpi_present_day_shift :", kpis_old.get("kpi_present_day_shift"))
print("kpi_total_night_shift :", kpis_old.get("kpi_total_night_shift"))
print("kpi_present_night_shift:", kpis_old.get("kpi_present_night_shift"))
print("kpi_absent            :", kpis_old.get("kpi_absent"))
print("kpi_on_leave          :", kpis_old.get("kpi_on_leave"))

# Let's count how many records have valid in_time by shift
day_in_count = 0
night_in_count = 0
for r in records:
    in_t = r.get("In Time") or r.get("in_time")
    sh = str(r.get("Shift") or "")
    if in_t and str(in_t).strip() not in ("00:00", "—", "", "None"):
        if "Night" in sh:
            night_in_count += 1
        else:
            day_in_count += 1

print("\n=== EXPECTED PRESENT BREAKDOWN BY IN_TIME ===")
print("Day Shift Check-Ins  :", day_in_count)
print("Night Shift Check-Ins:", night_in_count)
print("Total Check-Ins      :", day_in_count + night_in_count)
