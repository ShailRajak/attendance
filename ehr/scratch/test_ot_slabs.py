import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.utils.formatter import calculate_validated_ot

print("=== TESTING OVERTIME (OT) 30-MINUTE SLAB ROUNDING POLICY ===")

# Day Shift Tests (Shift End: 18:00)
t1 = calculate_validated_ot("18:20", "Day Shift")
print(f"Check-Out 18:20 (20m past 18:00) -> OT: {t1}h (Expected: 0.5h)")

t2 = calculate_validated_ot("18:50", "Day Shift")
print(f"Check-Out 18:50 (50m past 18:00) -> OT: {t2}h (Expected: 1.0h)")

t3 = calculate_validated_ot("19:20", "Day Shift")
print(f"Check-Out 19:20 (1h 20m / 80m past 18:00) -> OT: {t3}h (Expected: 1.5h)")

t4 = calculate_validated_ot("19:50", "Day Shift")
print(f"Check-Out 19:50 (1h 50m / 110m past 18:00) -> OT: {t4}h (Expected: 2.0h)")

t5 = calculate_validated_ot("17:50", "Day Shift")
print(f"Check-Out 17:50 (10m before 18:00) -> OT: {t5}h (Expected: 0.0h)")

t6 = calculate_validated_ot("18:10", "Day Shift")
print(f"Check-Out 18:10 (10m past 18:00) -> OT: {t6}h (Expected: 0.0h)")

# Night Shift Tests (Shift End: 08:00 AM)
t7 = calculate_validated_ot("08:20", "Night Shift")
print(f"Night Shift Check-Out 08:20 (20m past 08:00) -> OT: {t7}h (Expected: 0.5h)")

t8 = calculate_validated_ot("08:50", "Night Shift")
print(f"Night Shift Check-Out 08:50 (50m past 08:00) -> OT: {t8}h (Expected: 1.0h)")

t9 = calculate_validated_ot("09:20", "Night Shift")
print(f"Night Shift Check-Out 09:20 (1h 20m past 08:00) -> OT: {t9}h (Expected: 1.5h)")

assert t1 == 0.5, f"Expected 0.5, got {t1}"
assert t2 == 1.0, f"Expected 1.0, got {t2}"
assert t3 == 1.5, f"Expected 1.5, got {t3}"
assert t4 == 2.0, f"Expected 2.0, got {t4}"
assert t5 == 0.0, f"Expected 0.0, got {t5}"
assert t6 == 0.0, f"Expected 0.0, got {t6}"
assert t7 == 0.5, f"Expected 0.5, got {t7}"
assert t8 == 1.0, f"Expected 1.0, got {t8}"
assert t9 == 1.5, f"Expected 1.5, got {t9}"

print("\nSUCCESS: All OT Slab assertions passed 100% perfectly!")
