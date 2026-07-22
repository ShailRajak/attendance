import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth.models import User
from attendance.services.analytics_service import get_overtime_dashboard_data

cache.clear()

admin_user = User.objects.filter(username="Admin").first() or User.objects.first()

print("=== TESTING DAILY OVERTIME DASHBOARD DATA ===")
daily_params = {"period": "daily"}
daily_ctx = get_overtime_dashboard_data(user=admin_user, get_params=daily_params)
print("Period Text :", daily_ctx.get("period_text"))
print("Start Date  :", daily_ctx.get("start_date"))
print("End Date    :", daily_ctx.get("end_date"))
summary_d = daily_ctx.get("summary", {})
print("Card Punch OT:", summary_d.get("card_punch_ot"))
print("Requested OT :", summary_d.get("requested_ot"))
print("Weekend OT   :", summary_d.get("weekend_ot"))
print("Holiday OT   :", summary_d.get("holiday_ot"))
print("Total OT     :", summary_d.get("total_ot"))

print("\n=== TESTING WEEKLY OVERTIME DASHBOARD DATA ===")
weekly_params = {"period": "weekly"}
weekly_ctx = get_overtime_dashboard_data(user=admin_user, get_params=weekly_params)
print("Period Text :", weekly_ctx.get("period_text"))
print("Start Date  :", weekly_ctx.get("start_date"))
print("End Date    :", weekly_ctx.get("end_date"))
summary_w = weekly_ctx.get("summary", {})
print("Card Punch OT:", summary_w.get("card_punch_ot"))
print("Requested OT :", summary_w.get("requested_ot"))
print("Weekend OT   :", summary_w.get("weekend_ot"))
print("Holiday OT   :", summary_w.get("holiday_ot"))
print("Total OT     :", summary_w.get("total_ot"))
print("Daily Breakdown count:", len(summary_w.get("daily_breakdown", [])))
for db_item in summary_w.get("daily_breakdown", []):
    print("  Day:", db_item)
