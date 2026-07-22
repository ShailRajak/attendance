import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from attendance.services.attendance_service import (
    fetch_attendance_from_db,
    compute_weekly_kpi_cards,
)
from attendance.services.analytics_service import calculate_section_dashboard_stats

cache.clear()

records = fetch_attendance_from_db(None, "2026-07-20", "2026-07-26")

t0 = time.time()
weekly_kpis = compute_weekly_kpi_cards(records)
t1 = time.time()
print(f"compute_weekly_kpi_cards Time: {t1 - t0:.4f}s")

t2 = time.time()
stats = calculate_section_dashboard_stats(records, "Admin", "", "Admin", period="weekly")
t3 = time.time()
print(f"calculate_section_dashboard_stats Time: {t3 - t2:.4f}s")
