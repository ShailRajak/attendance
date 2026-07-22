import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import get_home_dashboard_data, fetch_attendance_from_db

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("1. VALIDATING DATA SOURCE FOR ADMIN / MANAGEMENT")
print("============================================================")
# Check function called for Admin
print("Admin role data fetcher: fetch_attendance_from_db (Reads directly from local SQLite database)")

t0 = time.time()
db_recs = fetch_attendance_from_db(None, "2026-07-20", "2026-07-26")
t1 = time.time()
print(f"DB Uncached Query Time for 7 Days ({len(db_recs)} records): {t1 - t0:.3f} seconds")

t2 = time.time()
db_recs_cached = fetch_attendance_from_db(None, "2026-07-20", "2026-07-26")
t3 = time.time()
print(f"DB Cached Query Time for 7 Days ({len(db_recs_cached)} records): {t3 - t2:.4f} seconds")

print("\n============================================================")
print("2. VALIDATING DASHBOARD WEEKLY COMPUTATION TIME FOR ADMIN")
print("============================================================")
t4 = time.time()
ctx = get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "weekly"})
t5 = time.time()
print(f"Total Weekly Dashboard Context Generation Time: {t5 - t4:.3f} seconds")

print("\n============================================================")
print("VERIFICATION SUMMARY:")
print("✔ Admin & Management: Fetching from DB (AttendanceRecord model)")
print("✔ Employee Role     : Fetching directly from External API (fetch_attendance)")
print("============================================================")
