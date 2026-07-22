import os
import sys
import django
from datetime import datetime

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance_from_db, parse_date
from attendance.utils.date_helpers import get_attendance_date_range

start_dt, end_dt = get_attendance_date_range()
start_str = start_dt.strftime("%Y-%m-%d")
end_str = end_dt.strftime("%Y-%m-%d")
print(f"Testing Monthly Period: {start_str} to {end_str}")

records = fetch_attendance_from_db(None, start_str, end_str)
print(f"Total fetched DB records: {len(records)}")

emp_records = {}
for r in records:
    emp_id = r.get("Employee ID")
    if not emp_id:
        continue
    if emp_id not in emp_records:
        emp_records[emp_id] = []
    emp_records[emp_id].append(r)

late_employees = []
for emp_id, log_list in emp_records.items():
    sorted_logs = sorted(log_list, key=lambda x: parse_date(x.get("Date")) or datetime.min)
    
    allowed_count = 0
    allowed_mins = 0.0
    unexcused_lates = []
    excused_lates = []
    
    for r in sorted_logs:
        in_time = r.get("In Time", "").strip()
        shift = r.get("Shift", "")
        late_min_val = float(r.get("Late Minutes") or 0.0)
        
        late_by_time = 0.0
        if in_time and ":" in in_time and in_time not in ("00:00", "—"):
            try:
                h, m = map(int, in_time.split(":"))
                shift_start = 20 * 60 if "Night" in shift else 9 * 60
                if h * 60 + m > shift_start:
                    late_by_time = float((h * 60 + m) - shift_start)
            except:
                pass
        
        late_mins = max(late_min_val, late_by_time)
        if late_mins > 0:
            if allowed_count < 3 and (allowed_mins + late_mins) <= 60.0:
                allowed_count += 1
                allowed_mins += late_mins
                excused_lates.append((r.get("Date"), late_mins))
            else:
                unexcused_lates.append((r.get("Date"), late_mins))
                
    if len(excused_lates) > 0 or len(unexcused_lates) > 0:
        emp_name = sorted_logs[0].get("Employee Name", emp_id)
        late_employees.append((emp_id, emp_name, len(excused_lates), allowed_mins, len(unexcused_lates)))

print(f"Total employees with late check-ins: {len(late_employees)}")
print("\nSample Late Policy Evaluation (First 10 employees):")
print(f"{'EMP ID':<10} | {'NAME':<25} | {'EXCUSED LATES':<15} | {'EXCUSED MINS':<15} | {'UNEXCUSED LATES':<15}")
print("-" * 85)
for emp in late_employees[:10]:
    print(f"{emp[0]:<10} | {emp[1]:<25} | {emp[2]:<15} | {emp[3]:<15.1f} | {emp[4]:<15}")
