import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance_from_db

records = fetch_attendance_from_db(None, "2026-07-20", "2026-07-20")
print(f"Inspecting {len(records)} records for 2026-07-20...")

sample_in_times = set()
sample_out_times = set()
sample_dates = set()
sample_shifts = set()
has_in_count = 0

for r in records[:50]:
    in_t = r.get("In Time") or r.get("in_time")
    out_t = r.get("Out Time") or r.get("out_time")
    dt = r.get("Date") or r.get("attendance_date")
    sh = r.get("Shift") or r.get("shift")
    if in_t and str(in_t).strip() not in ("00:00", "—", ""):
        has_in_count += 1
    sample_in_times.add(str(in_t))
    sample_out_times.add(str(out_t))
    sample_dates.add(str(dt))
    sample_shifts.add(str(sh))

print("Sample Dates in records:", sample_dates)
print("Sample Shifts in records:", sample_shifts)
print("Sample In Times:", list(sample_in_times)[:10])
print("Sample Out Times:", list(sample_out_times)[:10])
print("Count of non-empty in_time in first 50 records:", has_in_count)

total_has_in = sum(1 for r in records if (r.get("In Time") or r.get("in_time")) and str(r.get("In Time") or r.get("in_time")).strip() not in ("00:00", "—", ""))
print("TOTAL records with non-empty in_time on 2026-07-20:", total_has_in)
