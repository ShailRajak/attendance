import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.analytics_service import get_overtime_dashboard_data, get_leaves_dashboard_data

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print(f"Testing analytics views for user: {admin_user.username}")

# 1. Overtime dashboard without custom dates
ot_ctx = get_overtime_dashboard_data(user=admin_user, get_params={})
print("Overtime default period:", ot_ctx.get("period"), ot_ctx.get("start_date_str"), ot_ctx.get("end_date_str"))

# 2. Overtime dashboard with custom dates
ot_custom_ctx = get_overtime_dashboard_data(user=admin_user, get_params={"start_date": "2026-07-20", "end_date": "2026-07-20"})
print("Overtime custom period :", ot_custom_ctx.get("period"), ot_custom_ctx.get("start_date_str"), ot_custom_ctx.get("end_date_str"))

# 3. Leaves dashboard
leaves_ctx = get_leaves_dashboard_data(user=admin_user, period=None, cycle_num=None, week_num=None, year=None, query_employee_id=None)
print("Leaves default period  :", leaves_ctx.get("period"), leaves_ctx.get("start_str"), leaves_ctx.get("end_str"))

print("\nSUCCESS: All analytics views tested cleanly without NameError!")
