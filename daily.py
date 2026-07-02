import requests
import json
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "http://10.61.248.6:18010/RESTService/Search"

START_DATE = "2026-06-22"
END_DATE = "2026-06-22"

headers = {
    "Content-Type": "text"
}

all_records = []

current = datetime.strptime(START_DATE, "%Y-%m-%d")
end = datetime.strptime(END_DATE, "%Y-%m-%d")

while current <= end:

    date_api = current.strftime("%Y-%m-%d")

    print(f"Fetching {date_api}...")

    payload = {
        "FunID": "KQ062001",
        "Language": 3,
        "Data": {
            "YYMMDD": date_api
        }
    }

    try:

        response = requests.post(
            BASE_URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=120
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

            if data:
                all_records.extend(data)

            print(f"  -> {len(data)} rows")

        else:
            print(result.get("Message"))

    except Exception as e:
        print(e)

    current += timedelta(days=1)

print(f"\nTotal Rows : {len(all_records)}")

if all_records:

    df = pd.json_normalize(all_records)

    filename = f"Attendance_{START_DATE}_{END_DATE}.xlsx"

    df.to_excel(filename, index=False)

    print(f"Excel Saved : {filename}")

else:
    print("No records found.")