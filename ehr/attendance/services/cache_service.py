import logging
from datetime import datetime, date
from django.core.cache import cache

logger = logging.getLogger(__name__)

def generate_cache_key(user, employee_id, start_date, end_date):
    """
    Generates a unique cache key based on role, scope, employee, and date range.
    Format:
    - attendance:employee:<emp_id>:<start_date>:<end_date>
    - attendance:section:<section_name>:<start_date>:<end_date>
    - attendance:admin:ALL:<start_date>:<end_date>
    """
    if isinstance(start_date, (datetime, date)):
        start_date_str = start_date.strftime("%Y-%m-%d")
    else:
        start_date_str = str(start_date)

    if isinstance(end_date, (datetime, date)):
        end_date_str = end_date.strftime("%Y-%m-%d")
    else:
        end_date_str = str(end_date)

    from attendance.services.rbac_service import RBACService
    from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4

    is_superuser = user.is_superuser
    scope = RBACService.get_scope(user)
    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

    if employee_id:
        return f"attendance:employee:{employee_id}:{start_date_str}:{end_date_str}"

    if not is_supervisor or scope == "OWN":
        return f"attendance:employee:{user.username}:{start_date_str}:{end_date_str}"

    if is_superuser or scope == "ALL":
        return f"attendance:admin:ALL:{start_date_str}:{end_date_str}"

    role_obj, section_obj = resolve_user_role_and_section(user)
    expected_dtname4 = get_expected_dtname4(role_obj, section_obj, user.username)

    if expected_dtname4:
        scope_name = expected_dtname4.replace(" ", "_")
        return f"attendance:section:{scope_name}:{start_date_str}:{end_date_str}"

    return f"attendance:supervisor:{user.username}:{start_date_str}:{end_date_str}"


def get_db_metadata():
    """
    Query database metadata to check cache freshness.
    Caches the metadata for 60 seconds (1 minute validation TTL) to limit SQLite queries.
    """
    from django.db.models import Max, Count
    from attendance.models import AttendanceRecord

    metadata_cache_key = "attendance_db_metadata"
    cached_metadata = cache.get(metadata_cache_key)
    if cached_metadata is not None:
        return cached_metadata

    start_time = datetime.now()
    try:
        agg = AttendanceRecord.objects.aggregate(
            max_updated=Max("updated_at"),
            max_id=Max("id"),
            row_count=Count("id")
        )
        max_updated_str = agg["max_updated"].isoformat() if agg["max_updated"] else ""
        metadata = {
            "max_updated": max_updated_str,
            "max_id": agg["max_id"] or 0,
            "row_count": agg["row_count"] or 0
        }
    except Exception as e:
        logger.error("Error querying db metadata: %s", e)
        metadata = {
            "max_updated": "",
            "max_id": 0,
            "row_count": 0
        }

    duration = (datetime.now() - start_time).total_seconds()
    logger.info("DB QUERY EXECUTED: Metadata query completed in %.4fs (DB Query Duration)", duration)

    cache.set(metadata_cache_key, metadata, timeout=60)
    return metadata


def get_attendance_cache(cache_key):
    """
    Gets cached attendance records, validating its freshness metadata.
    Extends cache TTL by 15 minutes (900 seconds) if validation passes.
    """
    start_time = datetime.now()
    entry = cache.get(cache_key)
    read_duration = (datetime.now() - start_time).total_seconds()
    logger.info("Cache Read Duration: %.4fs", read_duration)

    if entry is None:
        logger.info("Cache MISS: Key %s not found in cache", cache_key)
        return None

    # Validate freshness
    current_metadata = get_db_metadata()
    cached_metadata = entry.get("metadata")

    if cached_metadata == current_metadata:
        logger.info("Validation PASSED: Cache entry is fresh. Extending TTL.")
        # Extend cache TTL for 15 minutes (900 seconds)
        cache.set(cache_key, entry, timeout=900)
        logger.info("Cache HIT: Key %s loaded from cache", cache_key)
        return entry.get("data")
    else:
        logger.info("Validation FAILED: Database metadata has changed. Invalidate cache.")
        logger.info("Cache INVALIDATED: Key %s is stale", cache_key)
        delete_attendance_cache(cache_key)
        return None


def set_attendance_cache(cache_key, data, timeout=900):
    """
    Sets attendance records and current database metadata to cache.
    """
    current_metadata = get_db_metadata()
    entry = {
        "metadata": current_metadata,
        "data": data
    }
    cache.set(cache_key, entry, timeout=timeout)
    logger.info("Cache REFRESH: Cached %d records under key %s with TTL %ds", len(data), cache_key, timeout)


def delete_attendance_cache(cache_key):
    """
    Deletes the attendance cache entry for the given key.
    """
    cache.delete(cache_key)


def invalidate_cache():
    """
    Invalidates cached metadata globally, forcing next reads to refresh.
    """
    cache.delete("attendance_db_metadata")
    logger.info("Cache INVALIDATED: Global database metadata cache cleared.")


def refresh_cache(user, employee_id, start_date, end_date):
    """
    Forces a cache reload by invalidating metadata, fetching from DB, and updating cache.
    """
    start_time = datetime.now()
    invalidate_cache()
    cache_key = generate_cache_key(user, employee_id, start_date, end_date)
    
    from attendance.services.attendance_service import fetch_attendance_from_db, fetch_attendance
    from attendance.services.rbac_service import RBACService
    
    scope = RBACService.get_scope(user)
    is_superuser = user.is_superuser
    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))
    
    # Query database or API
    if is_supervisor:
        db_start = datetime.now()
        data = fetch_attendance_from_db(employee_id, start_date, end_date, user=user)
        db_duration = (datetime.now() - db_start).total_seconds()
        logger.info("DB Query Duration: %.4fs (DB Query Duration)", db_duration)
    else:
        fetch_emp_id = employee_id if employee_id else user.username
        if fetch_emp_id != user.username:
            fetch_emp_id = user.username
        data = fetch_attendance(fetch_emp_id, start_date, end_date)

    set_attendance_cache(cache_key, data)
    refresh_duration = (datetime.now() - start_time).total_seconds()
    logger.info("Refresh Duration: %.4fs (Refresh Duration)", refresh_duration)
    return data


def get_or_create_attendance_cache(user, employee_id, start_date, end_date):
    """
    Coordinates cache checks: returns cached data on HIT, fetches and caches on MISS/stale.
    """
    cache_key = generate_cache_key(user, employee_id, start_date, end_date)
    data = get_attendance_cache(cache_key)
    if data is not None:
        return data
        
    # Cache MISS or INVALIDATED: Fetch and cache
    return refresh_cache(user, employee_id, start_date, end_date)
