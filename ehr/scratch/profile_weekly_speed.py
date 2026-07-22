import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.attendance_service import (
    get_home_dashboard_data,
    fetch_attendance_from_db,
    compute_weekly_kpi_cards,
    compute_kpi_cards,
    evaluate_monthly_late_policy
)
from attendance.services.analytics_service import calculate_section_dashboard_stats

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("============================================================")
print("PROFILING WEEKLY DASHBOARD EXECUTION TIME STEP-BY-STEP")
print("============================================================")

t0 = time.time()
records = fetch_attendance_from_db(None, "2026-07-20", "2026-07-26")
t1 = time.time()
print(f"1. fetch_attendance_from_db (18,271 records) : {t1 - t0:.4f} seconds")

t2 = time.time()
weekly_kpis = compute_weekly_kpi_cards(records)
t3 = time.time()
print(f"2. compute_weekly_kpi_cards                   : {t3 - t2:.4f} seconds")

t4 = time.time()
stats = calculate_section_dashboard_stats(records, "Admin", "", "Admin", period="weekly")
t5 = time.time()
print(f"3. calculate_section_dashboard_stats          : {t5 - t4:.4f} seconds")

t6 = time.time()
records_policy = evaluate_monthly_late_policy(records)
t7 = time.time()
print(f"4. evaluate_monthly_late_policy              : {t7 - t6:.4f} seconds")
