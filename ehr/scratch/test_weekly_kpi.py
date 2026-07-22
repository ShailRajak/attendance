import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import compute_kpi_cards, compute_weekly_kpi_cards, fetch_attendance_from_db

# Fetch a week's data (Week of 2026-07-20 to 2026-07-26)
start_str = "2026-07-20"
end_str = "2026-07-26"
records = fetch_attendance_from_db(None, start_str, end_str)

print(f"Total raw records fetched for week ({start_str} to {end_str}): {len(records)}")

# Group records by Date to see daily breakdown
records_by_date = {}
for r in records:
    dt = r.get("Date") or r.get("attendance_date")
    if dt:
        if dt not in records_by_date:
            records_by_date[dt] = []
        records_by_date[dt].append(r)

print(f"Number of days in week: {len(records_by_date)}")
daily_kpis = {}
for dt, daily_recs in sorted(records_by_date.items()):
    daily_kpis[dt] = compute_kpi_cards(daily_recs)
    print(f"  Date {dt}: Total Emp = {daily_kpis[dt]['kpi_total_employees']}, Present Day = {daily_kpis[dt]['kpi_present_day_shift']}, Present Night = {daily_kpis[dt]['kpi_present_night_shift']}, Absent = {daily_kpis[dt]['kpi_absent']}")

weekly_kpis = compute_weekly_kpi_cards(records)
print("\n=== WEEKLY SUMMED KPIS (ADMIN / MANAGEMENT) ===")
for k, v in weekly_kpis.items():
    print(f"  {k:<25}: {v}")
