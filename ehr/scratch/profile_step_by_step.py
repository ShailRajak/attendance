import os
import sys
import time
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.contrib.auth.models import User
from attendance.services import attendance_service, analytics_service

# Monkey patch or instrument get_home_dashboard_data
def profile_home():
    admin_user = User.objects.filter(username="Admin").first() or User.objects.first()
    t_start = time.time()
    
    # We will run get_home_dashboard_data with step timing inside
    import attendance.services.attendance_service as att_svc
    orig_fetch = att_svc.fetch_attendance_from_db
    
    def timed_fetch(*args, **kwargs):
        t0 = time.time()
        res = orig_fetch(*args, **kwargs)
        print(f"   [Step] fetch_attendance_from_db ({len(res)} records): {time.time() - t0:.3f}s")
        return res
    att_svc.fetch_attendance_from_db = timed_fetch

    orig_calc = analytics_service.calculate_section_dashboard_stats
    def timed_calc(*args, **kwargs):
        t0 = time.time()
        res = orig_calc(*args, **kwargs)
        print(f"   [Step] calculate_section_dashboard_stats: {time.time() - t0:.3f}s")
        return res
    analytics_service.calculate_section_dashboard_stats = timed_calc

    orig_kpi = att_svc.compute_weekly_kpi_cards
    def timed_kpi(*args, **kwargs):
        t0 = time.time()
        res = orig_kpi(*args, **kwargs)
        print(f"   [Step] compute_weekly_kpi_cards: {time.time() - t0:.3f}s")
        return res
    att_svc.compute_weekly_kpi_cards = timed_kpi

    print("Running get_home_dashboard_data...")
    res = att_svc.get_home_dashboard_data(admin_user, None, None, None, "dashboard", get_params={"period": "weekly"})
    print(f"Total Elapsed Time: {time.time() - t_start:.3f}s")

profile_home()
