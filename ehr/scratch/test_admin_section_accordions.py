import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.analytics_service import get_overtime_dashboard_data, get_leaves_dashboard_data

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("TESTING ADMIN SECTION ACCORDION PANELS IN OVERTIME & LEAVES")
print("============================================================")

# 1. Overtime Dashboard for Admin
ot_ctx = get_overtime_dashboard_data(admin_user, {})
print("Overtime Admin is_admin:", ot_ctx.get("is_admin"))
print("Overtime Admin is_section_view:", ot_ctx.get("is_section_view"))
print("Overtime Admin dept_panels count:", len(ot_ctx.get("dept_panels", [])))
print("Overtime Panels Sample:", [p[1] for p in ot_ctx.get("dept_panels", [])[:5]])

assert ot_ctx.get("is_admin") is True
assert len(ot_ctx.get("dept_panels", [])) > 1

# 2. Leaves Dashboard for Admin
leaves_ctx = get_leaves_dashboard_data(admin_user, "daily", None, None, 2026, None)
print("\nLeaves Admin is_admin:", leaves_ctx.get("is_admin"))
print("Leaves Admin is_section_view:", leaves_ctx.get("is_section_view"))
print("Leaves Admin dept_panels count:", len(leaves_ctx.get("dept_panels", [])))
print("Leaves Panels Sample:", [p[1] for p in leaves_ctx.get("dept_panels", [])[:5]])

assert leaves_ctx.get("is_admin") is True
assert len(leaves_ctx.get("dept_panels", [])) > 1

# 3. Verify Employee / Management Roles Untouched
emp_user = User.objects.filter(username="19105203").first()
if emp_user:
    emp_ot_ctx = get_overtime_dashboard_data(emp_user, {})
    print("\nEmployee Overtime is_admin:", emp_ot_ctx.get("is_admin"))
    print("Employee Overtime dept_panels count:", len(emp_ot_ctx.get("dept_panels", [])))
    assert emp_ot_ctx.get("is_admin") is False
    assert len(emp_ot_ctx.get("dept_panels", [])) == 0

print("\nALL TESTS PASSED SUCCESSFULLY! Section breakdown panels are active for Admin and untouched for other roles!")
