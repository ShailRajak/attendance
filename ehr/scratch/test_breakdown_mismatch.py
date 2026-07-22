import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.services.analytics_service import calculate_section_dashboard_stats
from attendance.services.attendance_service import fetch_attendance_from_db

records = fetch_attendance_from_db(None, "2026-07-21", "2026-07-21")

stats = calculate_section_dashboard_stats(records, role_display="Admin", section_display="Section-Wide")
print("=== PYTHON STATS FOR SINGLE DAY 2026-07-21 ===")
print("days_present:", stats.get("days_present"))
print("leaves_taken (top card ABSENT / LEAVES):", stats.get("leaves_taken"))
print("breakdown_data:", stats.get("breakdown_data"))
print("  index 0 (Present):", stats.get("breakdown_data")[0])
print("  index 1 (Leaves):", stats.get("breakdown_data")[1])
print("  index 2 (Rest Days):", stats.get("breakdown_data")[2])
print("  index 3 (Mispunches):", stats.get("breakdown_data")[3])
print("  index 4 (CL(0.5d)):", stats.get("breakdown_data")[4])
