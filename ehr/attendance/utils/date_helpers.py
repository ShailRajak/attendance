from datetime import date
from django.utils import timezone

def get_attendance_date_range(today=None):
    """
    Calculates the start and end dates for the current attendance cycle.

    Every attendance cycle starts on the 21st of a month and ends on the 20th of the following month.
    - If today's day is 21 or greater:
        - Start Date: 21st of the current month
        - End Date: Today
    - If today's day is less than 21:
        - Start Date: 21st of the previous month
        - End Date: Today

    Parameters:
        today (datetime.date, optional): A date object to calculate the range for.
                                         Defaults to Django's timezone.localdate() or date.today().

    Returns:
        tuple: (start_date, end_date) as datetime.date objects.
    """
    if today is None:
        try:
            # Respect timezone support if enabled in settings
            today = timezone.localdate()
        except Exception:
            today = date.today()

    if today.day >= 21:
        # Case 1: Today is 21st or later
        start_date = date(today.year, today.month, 21)
    else:
        # Case 2: Today is before the 21st (roll back to previous month)
        if today.month == 1:
            # January transitions back to December of the previous year
            start_date = date(today.year - 1, 12, 21)
        else:
            start_date = date(today.year, today.month - 1, 21)

    return start_date, today
