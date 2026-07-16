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
            # Fallback to local system date if Django is not initialized (e.g. in offline scripts)
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


def get_shift_start_minutes(wt_id, is_night_shift=False, in_time=None):
    """
    Translates the biometric working time ID (wt_id) to the shift start time in minutes since midnight.
    E.g., 480 for 08:00, 540 for 09:00.
    Falls back to heuristics if wt_id is unrecognized or missing.
    """
    wt_id_upper = str(wt_id or "").strip().upper()

    # Precise mappings from database analysis
    if wt_id_upper == 'Z07':
        return 7 * 60          # 07:00
    elif wt_id_upper == 'Z09':
        return 7 * 60 + 30     # 07:30
    elif wt_id_upper in ('B02', 'F02', 'F03', 'Z11'):
        return 8 * 60          # 08:00
    elif wt_id_upper in ('B03', 'H11', 'H15', 'Y01'):
        return 8 * 60 + 30     # 08:30
    elif wt_id_upper in ('X01', 'Z01'):
        return 9 * 60          # 09:00
    elif wt_id_upper == 'Z03':
        return 9 * 60 + 30     # 09:30
    elif wt_id_upper == 'Z08':
        return 19 * 60         # 19:00
    elif wt_id_upper == 'Z10':
        return 19 * 60 + 30    # 19:30
    elif wt_id_upper in ('D02', 'F04', 'H14'):
        return 20 * 60         # 20:00
    elif wt_id_upper in ('D03', 'F06', 'Y02', 'H16'):
        return 20 * 60 + 30    # 20:30
    elif wt_id_upper == 'Z04':
        return 21 * 60 + 30    # 21:30

    # Heuristics if wt_id is missing or unknown
    if in_time and ":" in in_time:
        try:
            h, m = map(int, in_time.split(":"))
            check_in_min = h * 60 + m
            if is_night_shift:
                # Night shift timing heuristic (normally 20:00 or 20:30)
                if check_in_min < 20 * 60 + 15:
                    return 20 * 60
                else:
                    return 20 * 60 + 30
            else:
                # Day shift timing heuristic (normally 8:00 or 9:00)
                if check_in_min < 8 * 60 + 30:
                    return 8 * 60
                else:
                    return 9 * 60
        except Exception:
            pass

    # Default fallback
    return 20 * 60 if is_night_shift else 9 * 60

