from datetime import date
import sys
import os

# Add the project directory to sys.path so we can import django/app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up minimal Django settings context if needed
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ehr.settings")

from attendance.utils.date_helpers import get_attendance_date_range

# Test cases: (test_date, description)
test_cases = [
    # Standard Case 1: today is 21st or greater
    (date(2026, 6, 28), "Today is 28 June 2026 (day >= 21)"),
    (date(2026, 6, 21), "Today is 21 June 2026 (boundary day = 21)"),
    
    # Standard Case 2: today is less than 21
    (date(2026, 6, 18), "Today is 18 June 2026 (day < 21)"),
    (date(2026, 6, 20), "Today is 20 June 2026 (boundary day = 20)"),
    
    # Edge Case: January to December year transition
    (date(2026, 1, 5), "Today is 5 January 2026 (roll back to December 2025)"),
    (date(2026, 1, 21), "Today is 21 January 2026 (start of cycle in January)"),
    
    # Edge Case: Leap year transitions (February 2028 - 29 days)
    (date(2028, 2, 29), "Today is 29 February 2028 (leap year boundary >= 21)"),
    (date(2028, 3, 5), "Today is 5 March 2028 (roll back to 21 Feb in leap year)"),
    
    # Edge Case: Non-leap year February transition
    (date(2027, 3, 5), "Today is 5 March 2027 (roll back to 21 Feb in non-leap year)"),
]

print("=" * 75)
print("TESTING get_attendance_date_range() RESULTS:")
print("=" * 75)

for test_date, desc in test_cases:
    start, end = get_attendance_date_range(test_date)
    print(f"Description: {desc}")
    print(f"Input Date : {test_date.strftime('%d %B %Y')} (day={test_date.day})")
    print(f"Output     : Start={start.strftime('%d %B %Y')}, End={end.strftime('%d %B %Y')}")
    print("-" * 75)
