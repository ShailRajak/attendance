from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json

import requests

from attendance.utils.formatter import filter_attendance_data

# Caching imports removed (handled by get_attendance)

def get_attendance_api_url():
    """
    Retrieve the configured Attendance API base URL dynamically.
    Falls back to http://10.61.248.6:18010/RESTService/Search if database/migration is not ready or configuration is not set.
    """
    try:
        from attendance.models import AttendanceAPIConfig
        config = AttendanceAPIConfig.objects.first()
        if config:
            api_url = config.api_url.strip().rstrip('/')
            port = config.port
            return f"{api_url}:{port}/RESTService/Search"
    except Exception:
        # Fallback to the default hardcoded values if table/migration is not yet ready or other errors occur
        pass
    return "http://10.61.248.6:18010/RESTService/Search"


HEADERS = {"Content-Type": "text"}
CACHE_TIMEOUT = 60 * 60


def _fetch_single_date(date_obj, employee_id):
    """
    Helper function to fetch attendance records for a single date.
    """
    date_str = date_obj.strftime("%Y%m%d")
    print(f"Fetching : {date_str}")

    data_payload = {"YYMMDD": date_str}

    if employee_id:
        data_payload["EmpNo"] = employee_id

    payload = {"FunID": "KQ062001", "Language": 3, "Data": data_payload}

    request_timeout = 15 if employee_id else 120

    base_url = get_attendance_api_url()

    retries = 3
    for attempt in range(retries):
        try:
            response = requests.post(
                base_url,
                data=json.dumps(payload),
                headers=HEADERS,
                timeout=request_timeout,
            )

            response.raise_for_status()
            result = response.json()

            if result.get("Success"):
                data = result.get("Data", [])

                if isinstance(data, str):
                    data = json.loads(data)

                if isinstance(data, dict):
                    if "Table" in data:
                        data = data["Table"]
                    elif "Rows" in data:
                        data = data["Rows"]
                    else:
                        data = list(data.values())[0]

                if isinstance(data, list):
                    return data
            else:
                print(
                    f"API Error ({date_str}) (Attempt {attempt+1}/{retries}) : "
                    f"{result.get('Message', 'Unknown Error')}"
                )

        except requests.exceptions.RequestException as e:
            print(f"Request Error ({date_str}) (Attempt {attempt+1}/{retries}) : {e}")
            if attempt < retries - 1:
                import time

                time.sleep(0.5)

        except Exception as e:
            print(
                f"Unexpected Error ({date_str}) (Attempt {attempt+1}/{retries}) : {e}"
            )
            break

    return []


def fetch_attendance_from_db(employee_id, start_date, end_date, user=None):
    """
    Retrieve attendance records from the local synchronized database.
    """
    from attendance.models import AttendanceRecord

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif isinstance(end_date, datetime):
        end_date = end_date.date()

    qs = AttendanceRecord.objects.filter(attendance_date__range=(start_date, end_date))

    if user and not user.is_superuser:
        from attendance.services.rbac_service import RBACService
        from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4

        scope = RBACService.get_scope(user)
        role, section = resolve_user_role_and_section(user)
        is_supervisor = (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

        if scope == "OWN" or not is_supervisor:
            qs = qs.filter(employee_id=user.username)
        elif scope != "ALL":
            expected_dtname4 = get_expected_dtname4(role, section, user.username)
            if expected_dtname4:
                qs = qs.filter(day=expected_dtname4)
                if employee_id:
                    qs = qs.filter(employee_id=employee_id)
            else:
                accessible_users = list(
                    RBACService.get_accessible_employees(user).values_list("user__username", flat=True)
                )
                if employee_id:
                    if employee_id in accessible_users:
                        qs = qs.filter(employee_id=employee_id)
                    else:
                        return []
                else:
                    qs = qs.filter(employee_id__in=accessible_users)
        else: # scope == "ALL"
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
    else:
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

    # Sort descending by date
    qs = qs.order_by("-attendance_date", "employee_id")

    fields = [
        "attendance_date", "employee_id", "employee_name", "in_time", "out_time",
        "working_hours", "card_punch_ot", "shift", "leave_type", "late_minutes", "day",
        "requested_ot", "weekend_ot", "holiday_ot", "ot4", "total_ot_all", "req_overtime", "approved_ot",
        "wt_id", "wt_type_no", "attendance_source", "attendance_status", "mobile", "workday", "weekday"
    ]

    def format_float(val):
        if val is None:
            return ""
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)

    return [
        {
            "Date": r["attendance_date"].strftime("%d-%m-%Y") if r["attendance_date"] else "",
            "Employee ID": r["employee_id"],
            "Employee Name": r["employee_name"],
            "In Time": r["in_time"],
            "Out Time": r["out_time"],
            "Working Hours": format_float(r["working_hours"]),
            "Card Punch OT": format_float(r["card_punch_ot"]),
            "Requested OT": format_float(r["requested_ot"]),
            "Weekend OT": format_float(r["weekend_ot"]),
            "Holiday OT": format_float(r["holiday_ot"]),
            "OT4": format_float(r["ot4"]),
            "Total OT All": format_float(r["total_ot_all"]),
            "Req OverTime": format_float(r["req_overtime"]),
            "Approved OT": format_float(r["approved_ot"]),
            "WT ID": r["wt_id"],
            "WT Type No": r["wt_type_no"],
            "Attendance Source": r["attendance_source"],
            "Day": r["day"],
            "Attendance Status": r["attendance_status"],
            "Shift": r["shift"],
            "Mobile": r["mobile"],
            "Late Minutes": format_float(r["late_minutes"]),
            "Leave Type": r["leave_type"],
            "WorkDay": r["workday"],
            "Weekday": r["weekday"],
        }
        for r in qs.values(*fields)
    ]


def fetch_attendance(employee_id, start_date, end_date):
    """
    Fetch attendance data from Attendance REST API.
    Pure fetcher: caching is managed centrally at get_attendance level.
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    print("=" * 60)
    print("Fetching attendance from API...")
    print("=" * 60)

    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)

    all_records = []

    max_workers = min(len(dates), 3) if dates else 1
    if max_workers > 0:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_fetch_single_date, dt, employee_id) for dt in dates
            ]
            for future in futures:
                try:
                    records = future.result()
                    all_records.extend(records)
                except Exception as exc:
                    print(f"Concurrent fetching generated an exception: {exc}")

    print(f"\nTotal Records : {len(all_records)}")

    filtered_data = filter_attendance_data(all_records)
    return filtered_data


def get_attendance(user, employee_id, start_date, end_date):
    """
    Centralized service to retrieve attendance records.
    Uses get_or_create_attendance_cache from the centralized cache service.
    """
    if user is None or not user.is_authenticated:
        return []

    from attendance.services.cache_service import get_or_create_attendance_cache
    return get_or_create_attendance_cache(user, employee_id, start_date, end_date)
