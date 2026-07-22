import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services.attendance_service import (
    fetch_attendance_from_db, evaluate_monthly_late_policy, compute_weekly_kpi_cards
)
from attendance.services.analytics_service import calculate_section_dashboard_stats

print("============================================================")
print("DEEP PROFILING SECTION STATS & WEEKLY KPI")
print("============================================================")

t0 = time.time()
records = fetch_attendance_from_db(employee_id="", start_date="2026-07-20", end_date="2026-07-26")
t1 = time.time()
print(f"1. DB Fetch ({len(records)} records): {t1 - t0:.3f}s")

t0 = time.time()
records_eval = evaluate_monthly_late_policy(records)
t2 = time.time()
print(f"2. evaluate_monthly_late_policy: {t2 - t0:.3f}s")

t0 = time.time()
stats = calculate_section_dashboard_stats(records_eval, "2026-07-20", "2026-07-26")
t3 = time.time()
print(f"3. calculate_section_dashboard_stats: {t3 - t0:.3f}s")

t0 = time.time()
kpi_cards = compute_weekly_kpi_cards(records_eval)
t4 = time.time()
print(f"4. compute_weekly_kpi_cards: {t4 - t0:.3f}s")
