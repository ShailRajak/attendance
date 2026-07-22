import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from attendance.views import login_view

rf = RequestFactory()

print("============================================================")
print("TESTING FORGOT PASSWORD FEATURE")
print("============================================================")

# 1. Create a dummy test user
test_emp_id = "99998888"
User.objects.filter(username=test_emp_id).delete()
user = User.objects.create_user(username=test_emp_id, password="OldPassword@123")

# 2. Test invalid employee ID
req1 = rf.post("/login/", {
    "action": "forgot_password",
    "reset_employee_id": "00000000",
    "new_password": "NewPassword@123",
    "confirm_password": "NewPassword@123"
})
req1.user = AnonymousUser()
setattr(req1, 'session', {})
messages = FallbackStorage(req1)
setattr(req1, '_messages', messages)
res1 = login_view(req1)
print("Non-existent user test response code:", res1.status_code)

# 3. Test successful password reset
req2 = rf.post("/login/", {
    "action": "forgot_password",
    "reset_employee_id": test_emp_id,
    "new_password": "NewPassword@123",
    "confirm_password": "NewPassword@123"
})
req2.user = AnonymousUser()
setattr(req2, 'session', {})
messages2 = FallbackStorage(req2)
setattr(req2, '_messages', messages2)
res2 = login_view(req2)
print("Successful reset response code:", res2.status_code)

# Verify updated user password
user.refresh_from_db()
assert user.check_password("NewPassword@123"), "Password check failed!"
print("Password updated and verified in database!")

# Cleanup test user
user.delete()

print("\nALL FORGOT PASSWORD TESTS PASSED SUCCESSFULLY!")
