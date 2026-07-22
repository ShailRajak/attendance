import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance_from_db

records = fetch_attendance_from_db(None, "2026-07-21", "2026-07-21")

emp_map = {}
for r in records:
    emp_id = r.get("Employee ID")
    if not emp_id:
        continue
    # Keep one record per unique employee
    if emp_id not in emp_map:
        emp_map[emp_id] = r

print(f"Total unique employee records: {len(emp_map)}")

present = 0
absent = 0
mispunch = 0
cl = 0

for emp_id, r in emp_map.items():
    in_t = r.get("In Time", "").strip()
    out_t = r.get("Out Time", "").strip()
    wt = float(r.get("Working Hours") or 0.0)
    has_in = bool(in_t) and in_t not in ("00:00", "—", "")
    has_out = bool(out_t) and out_t not in ("00:00", "—", "")
    
    is_mispunch = (has_in and not has_out) or (has_out and not has_in)
    
    if not has_in:
        absent += 1
    elif is_mispunch:
        mispunch += 1
    elif wt >= 8.0:
        present += 1
    else:
        cl += 1

print("=== UNIQUE EMPLOYEE BREAKDOWN ===")
print("Present :", present)
print("Absent  :", absent)
print("Mispunch:", mispunch)
print("CL(0.5d):", cl)
print("TOTAL   :", present + absent + mispunch + cl)
print("Absent (940) + CL (29) =", absent + cl)
