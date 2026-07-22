import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data
from attendance.services.analytics_service import get_overtime_dashboard_data, get_leaves_dashboard_data

print("============================================================")
print("TESTING SHIFT & LOCATION FILTER BUTTON ATTRIBUTES")
print("============================================================")

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

# 1. Home Dashboard
home_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", {"period": "daily"})
attendance = home_ctx.get("attendance", [])
print(f"Home Dashboard attendance count: {len(attendance)}")
assert len(attendance) > 0
for r in attendance[:10]:
    assert "location_label" in r, f"Missing location_label in row {r}"
    assert r["location_label"] in ("s63", "c39")
    assert "shift_label" in r, f"Missing shift_label in row {r}"
    assert r["shift_label"] in ("day", "night")
print("Sample Home Attendance Labels:", [(r["employee_id"], r["shift_label"], r["location_label"]) for r in attendance[:5]])

# 2. Overtime Dashboard
ot_ctx = get_overtime_dashboard_data(admin_user, {})
ot_employees = ot_ctx.get("scope_summary", {}).get("employees", [])
print(f"\nOvertime employees count: {len(ot_employees)}")
assert len(ot_employees) > 0
for emp in ot_employees[:10]:
    assert "location_label" in emp, f"Missing location_label in emp {emp}"
    assert emp["location_label"] in ("s63", "c39")
    assert "shift_label" in emp, f"Missing shift_label in emp {emp}"
    assert emp["shift_label"] in ("day", "night")
print("Sample Overtime Labels:", [(emp["emp_id"], emp["shift_label"], emp["location_label"]) for emp in ot_employees[:5]])

# 3. Leaves Dashboard
leaves_ctx = get_leaves_dashboard_data(admin_user, "daily", None, None, 2026, None)
records = leaves_ctx.get("records", [])
print(f"\nLeaves records count: {len(records)}")
assert len(records) > 0
for rec in records[:10]:
    assert "location_label" in rec, f"Missing location_label in rec {rec}"
    assert rec["location_label"] in ("s63", "c39")
    assert "shift_label" in rec, f"Missing shift_label in rec {rec}"
    assert rec["shift_label"] in ("day", "night")
print("Sample Leaves Labels:", [(rec["employee_id"], rec["shift_label"], rec["location_label"]) for rec in records[:5]])

print("\nALL SHIFT & LOCATION FILTER BUTTON TESTS PASSED 100% SUCCESSFULLY!")
