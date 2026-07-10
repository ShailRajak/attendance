from datetime import datetime

from django.core.cache import cache


def generate_attendance_cache_key(employee_id, start_date, end_date):
    """
    Generates a unique cache key based on employee ID and date range.
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    emp = employee_id if employee_id else "ALL"
    return (
        f"attendance_{emp}_"
        f"{start_date.strftime('%Y%m%d')}_"
        f"{end_date.strftime('%Y%m%d')}"
    )


def get_attendance_cache(cache_key):
    """
    Gets cached attendance records.
    """
    return cache.get(cache_key)


def set_attendance_cache(cache_key, data, timeout=3600):
    """
    Sets attendance records to cache.
    """
    cache.set(cache_key, data, timeout=timeout)
