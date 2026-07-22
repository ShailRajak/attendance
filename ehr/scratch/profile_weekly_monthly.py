import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data, fetch_attendance_from_db
from attendance.services.analytics_service import calculate_section_dashboard_stats

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("PROFILING WEEKLY & MONTHLY PERFORMANCE")
print("============================================================")

t0 = time.time()
fetch_attendance_from_db(employee_id="", start_date="2026-07-21", end_date="2026-07-22")
t1 = time.time()
print(f"1-Day DB Fetch Time: {t1 - t0:.3f}s")

t0 = time.time()
att_weekly = fetch_attendance_from_db(employee_id="", start_date="2026-07-20", end_date="2026-07-26")
t2 = time.time()
print(f"Weekly (7-Day) DB Fetch Time ({len(att_weekly)} records): {t2 - t0:.3f}s")

t0 = time.time()
stats = calculate_section_dashboard_stats(att_weekly, "2026-07-20", "2026-07-26")
t3 = time.time()
print(f"calculate_section_dashboard_stats Time: {t3 - t0:.3f}s")

t0 = time.time()
dash_ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "weekly"})
t4 = time.time()
print(f"Total Weekly get_home_dashboard_data Time: {t4 - t0:.3f}s")

t0 = time.time()
dash_ctx_m = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "monthly"})
t5 = time.time()
print(f"Total Monthly get_home_dashboard_data Time: {t5 - t0:.3f}s")
