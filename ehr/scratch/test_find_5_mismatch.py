import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.attendance_service import fetch_attendance_from_db
from attendance.services.analytics_service import parse_date

records = fetch_attendance_from_db(None, "2026-07-21", "2026-07-21")
print(f"Total single day records: {len(records)}")

status_counts = {}
for r in records:
    in_t = r.get("In Time", "").strip()
    out_t = r.get("Out Time", "").strip()
    shift = r.get("Shift", "")
    leave = r.get("Leave Type", "").strip()
    wt = float(r.get("Working Hours") or 0.0)
    has_in = bool(in_t) and in_t not in ("00:00", "—", "")
    has_out = bool(out_t) and out_t not in ("00:00", "—", "")
    
    # Check Python logic in calculate_section_dashboard_stats:
    # is_mispunch = (has_in and not has_out) or (has_out and not has_in)
    is_mispunch = (has_in and not has_out) or (has_out and not has_in)
    
    cat = "UNKNOWN"
    if not has_in:
        cat = "NO_IN_TIME (status_leave)"
    else:
        if is_mispunch:
            cat = "MISPUNCH"
        else:
            if wt >= 8.0:
                cat = "PRESENT"
            else:
                cat = "CL(0.5d) (status_cl)"
                
    status_counts[cat] = status_counts.get(cat, 0) + 1

print("\n=== CATEGORY BREAKDOWN IN PYTHON ===")
for cat, cnt in status_counts.items():
    print(f"{cat:<30}: {cnt}")
