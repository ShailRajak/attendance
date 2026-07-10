from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json

import requests

from attendance.utils.formatter import filter_attendance_data

from attendance.services.cache_service import (
    generate_attendance_cache_key,
    get_attendance_cache,
    set_attendance_cache,
)

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


def fetch_attendance(employee_id, start_date, end_date):
    """
    Fetch attendance data from Attendance REST API.
    Uses cache_service for reading/writing cached records.
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    cache_key = generate_attendance_cache_key(employee_id, start_date, end_date)
    cached_data = get_attendance_cache(cache_key)

    if cached_data is not None:
        print("=" * 60)
        print("Loaded attendance from CACHE")
        print(f"Cache Key : {cache_key}")
        print("=" * 60)
        return cached_data

    print("=" * 60)
    print("Cache MISS")
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

    set_attendance_cache(cache_key, filtered_data, timeout=CACHE_TIMEOUT)

    print("=" * 60)
    print("Attendance cached successfully")
    print(f"Cache Key : {cache_key}")
    print("=" * 60)

    return filtered_data
