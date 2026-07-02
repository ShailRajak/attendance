import json
import requests
from datetime import datetime, timedelta

from attendance.utils.formatter import filter_attendance_data


# ==========================================================
# API CONFIGURATION
# ==========================================================

BASE_URL = "http://10.61.248.6:18010/RESTService/Search"

HEADERS = {
    "Content-Type": "text"
}


# ==========================================================
# FETCH ATTENDANCE
# ==========================================================

def fetch_attendance(employee_id, start_date, end_date):
    """
    Fetch attendance data from the Attendance REST API.

    Parameters
    ----------
    employee_id : str

    start_date : str | datetime
        Example:
            "2026-03-21"

    end_date : str | datetime
        Example:
            "2026-04-20"

    Returns
    -------
    list
        Filtered attendance records
    """

    # -----------------------------------------
    # Convert string dates into datetime objects
    # -----------------------------------------

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    current_date = start_date

    all_records = []

    # -----------------------------------------
    # Loop through all dates
    # -----------------------------------------

    while current_date <= end_date:

        date_str = current_date.strftime("%Y%m%d")

        print(f"Fetching : {date_str}")

        payload = {
            "FunID": "KQ062001",
            "Language": 3,
            "Data": {
                "EmpNo": employee_id,
                "YYMMDD": date_str
            }
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

                # API sometimes returns JSON string
                if isinstance(data, str):

                    data = json.loads(data)

                # API sometimes returns Dictionary
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

        # Next Day
        current_date += timedelta(days=1)

    print(f"\nTotal Records : {len(all_records)}")

    # Filter required columns only
    return filter_attendance_data(all_records)