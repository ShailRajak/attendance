import json
import requests
from datetime import datetime, timedelta

from django.core.cache import cache

from attendance.utils.formatter import filter_attendance_data


# ==========================================================
# API CONFIGURATION
# ==========================================================

BASE_URL = "http://10.61.248.6:18010/RESTService/Search"

HEADERS = {
    "Content-Type": "text"
}

# Cache timeout (1 hour)
CACHE_TIMEOUT = 60 * 60


# ==========================================================
# FETCH ATTENDANCE
# ==========================================================

def fetch_attendance(employee_id, start_date, end_date):
    """
    Fetch attendance data from Attendance REST API.

    Uses Django cache so the API is called only once for the
    same employee/date range. Subsequent requests are served
    directly from cache.
    """

    # -----------------------------------------
    # Convert string dates into datetime objects
    # -----------------------------------------

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    # -----------------------------------------
    # Create cache key
    # -----------------------------------------

    emp = employee_id if employee_id else "ALL"

    cache_key = (
        f"attendance_{emp}_"
        f"{start_date.strftime('%Y%m%d')}_"
        f"{end_date.strftime('%Y%m%d')}"
    )

    # -----------------------------------------
    # Check Cache
    # -----------------------------------------

    cached_data = cache.get(cache_key)

    if cached_data is not None:
        print("=" * 60)
        print(f"Loaded attendance from CACHE")
        print(f"Cache Key : {cache_key}")
        print("=" * 60)
        return cached_data

    print("=" * 60)
    print(f"Cache MISS")
    print("Fetching attendance from API...")
    print("=" * 60)

    current_date = start_date
    all_records = []

    # -----------------------------------------
    # Loop through all dates
    # -----------------------------------------

    while current_date <= end_date:

        date_str = current_date.strftime("%Y%m%d")

        print(f"Fetching : {date_str}")

        data_payload = {
            "YYMMDD": date_str
        }

        if employee_id:
            data_payload["EmpNo"] = employee_id

        payload = {
            "FunID": "KQ062001",
            "Language": 3,
            "Data": data_payload
        }

        try:

            response = requests.post(
                BASE_URL,
                data=json.dumps(payload),
                headers=HEADERS,
                timeout=30
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
                    all_records.extend(data)

            else:

                print(
                    f"API Error ({date_str}) : "
                    f"{result.get('Message', 'Unknown Error')}"
                )

        except requests.exceptions.RequestException as e:

            print(f"Request Error ({date_str}) : {e}")

        except Exception as e:

            print(f"Unexpected Error ({date_str}) : {e}")

        current_date += timedelta(days=1)

    print(f"\nTotal Records : {len(all_records)}")

    filtered_data = filter_attendance_data(all_records)

    # -----------------------------------------
    # Save to Cache
    # -----------------------------------------

    cache.set(cache_key, filtered_data, timeout=CACHE_TIMEOUT)

    print("=" * 60)
    print("Attendance cached successfully")
    print(f"Cache Key : {cache_key}")
    print("=" * 60)

    return filtered_data