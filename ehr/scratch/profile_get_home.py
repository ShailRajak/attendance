import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("LINE-BY-LINE PROFILING OF get_home_dashboard_data")
print("============================================================")

t0 = time.time()
dash_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "weekly"})
t1 = time.time()
print(f"Weekly Total Time: {t1 - t0:.3f}s")
