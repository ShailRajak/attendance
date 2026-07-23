import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from attendance.models import Role, Section, Plant, UserProfile
from attendance.views import signup_view
from attendance.services.auth_service import validate_signup, register_user

print("============================================================")
print("TESTING NEW REGISTRATION MODULE (EMPLOYEE & MANAGEMENT ROLES)")
print("============================================================")

# 1. Verify Role Dropdown Options
roles = Role.objects.filter(is_active=True, code__in=["employee", "management"]).order_by("id")
role_codes = list(roles.values_list("code", flat=True))
role_names = list(roles.values_list("name", flat=True))

print("Active Registration Roles in View:", role_names)
assert role_codes == ["employee", "management"], f"Expected ['employee', 'management'], got {role_codes}"

# 2. Test Employee Registration (Without Section)
emp_id = "test_emp_9901"
User.objects.filter(username=emp_id).delete()

valid_emp, err_emp = validate_signup(
    employee_id=emp_id,
    password="Password@123",
    confirm_password="Password@123",
    role="employee",
    company="ismartu",
    plant="s63",
    department="",
    section="",
    team=""
)
print("Employee Validation (No Section):", valid_emp, "Error:", err_emp)
assert valid_emp is True, f"Employee validation failed: {err_emp}"

user_emp, err_reg_emp = register_user(
    employee_id=emp_id,
    password="Password@123",
    role="employee",
    company="ismartu",
    plant="s63",
    department="",
    section="",
    team=""
)
assert user_emp is not None, f"Employee registration failed: {err_reg_emp}"
assert user_emp.profile.role.code == "employee"
assert user_emp.profile.section is None
print("Employee User Created Successfully! Profile Role:", user_emp.profile.role.name, "| Section:", user_emp.profile.section)

# 3. Test Management Registration Without Section (Should Fail)
mgmt_id_fail = "test_mgmt_9902"
User.objects.filter(username=mgmt_id_fail).delete()

valid_mgmt_fail, err_mgmt_fail = validate_signup(
    employee_id=mgmt_id_fail,
    password="Password@123",
    confirm_password="Password@123",
    role="management",
    company="ismartu",
    plant="s63",
    department="",
    section="",
    team=""
)
print("Management Validation Without Section:", valid_mgmt_fail, "| Error Message:", err_mgmt_fail)
assert valid_mgmt_fail is False, "Management registration without section should fail!"
assert "Department is required" in err_mgmt_fail

# 4. Test Management Registration With Section (Should Succeed)
mgmt_id_pass = "test_mgmt_9903"
User.objects.filter(username=mgmt_id_pass).delete()
active_sec = Section.objects.filter(is_active=True).first()

valid_mgmt_pass, err_mgmt_pass = validate_signup(
    employee_id=mgmt_id_pass,
    password="Password@123",
    confirm_password="Password@123",
    role="management",
    company="ismartu",
    plant="s63",
    department="",
    section=active_sec.code,
    team=""
)
print(f"Management Validation With Section ({active_sec.code}):", valid_mgmt_pass, "| Error:", err_mgmt_pass)
assert valid_mgmt_pass is True

user_mgmt, err_reg_mgmt = register_user(
    employee_id=mgmt_id_pass,
    password="Password@123",
    role="management",
    company="ismartu",
    plant="s63",
    department="",
    section=active_sec.code,
    team=""
)
assert user_mgmt is not None, f"Management registration failed: {err_reg_mgmt}"
assert user_mgmt.profile.role.code == "management"
assert user_mgmt.profile.section == active_sec
print("Management User Created Successfully! Profile Role:", user_mgmt.profile.role.name, "| Linked Section:", user_mgmt.profile.section.name)

# Cleanup test users
User.objects.filter(username__in=[emp_id, mgmt_id_fail, mgmt_id_pass]).delete()

print("\nALL REGISTRATION TESTS PASSED 100% CLEANLY!")
