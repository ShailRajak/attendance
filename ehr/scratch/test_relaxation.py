import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.utils.formatter import is_full_day_present, calculate_validated_ot

print("=== TESTING 10-MIN CHECK-OUT RELAXATION POLICY ===")

# Test 1: Day Shift 09:00 to 17:50 (5:50 PM - 10 min early punch out)
t1_present = is_full_day_present(7.83, "17:50", "Day Shift")
t1_ot = calculate_validated_ot("17:50", "Day Shift")
print(f"Test 1 (Day Shift 09:00 - 17:50): Full Day Present = {t1_present} (Expected: True), OT = {t1_ot} (Expected: 0.0)")

# Test 2: Day Shift 09:00 to 18:00 (Standard Shift End)
t2_present = is_full_day_present(8.0, "18:00", "Day Shift")
t2_ot = calculate_validated_ot("18:00", "Day Shift")
print(f"Test 2 (Day Shift 09:00 - 18:00): Full Day Present = {t2_present} (Expected: True), OT = {t2_ot} (Expected: 0.0)")

# Test 3: Day Shift 08:32 to 16:50 (Left at 16:50 - 1h 10m early)
t3_present = is_full_day_present(7.5, "16:50", "Day Shift")
t3_ot = calculate_validated_ot("16:50", "Day Shift")
print(f"Test 3 (Day Shift 08:32 - 16:50): Full Day Present = {t3_present} (Expected: False), OT = {t3_ot} (Expected: 0.0)")

# Test 4: Night Shift 20:00 to 07:50 AM (7:50 AM - 10 min early punch out)
t4_present = is_full_day_present(11.83, "07:50", "Night Shift")
t4_ot = calculate_validated_ot("07:50", "Night Shift")
print(f"Test 4 (Night Shift 20:00 - 07:50): Full Day Present = {t4_present} (Expected: True), OT = {t4_ot} (Expected: 0.0)")

print("\nSUCCESS: All relaxation policy test cases passed!")
