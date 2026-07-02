import requests
import json
import pandas as pd
from datetime import datetime, timedelta

# ===========================
# CONFIGURATION
# ===========================
BASE_URL = "http://10.61.248.6:18010/RESTService/Search"

EMP_ID = "19105203"

START_DATE = "2026-03-21"
END_DATE = "2026-04-20"

headers = {
    "Content-Type": "text"
}

# ===========================
# REQUIRED COLUMNS (Yellow Highlighted)
# ===========================
REQUIRED_COLUMNS = [
    "YYMMDD",
    "EmpNo",
    "GO1",
    "OUT1",
    "OverTime",
    "OverTime1",
    "OverTime2",
    "OverTimeAll",
    "ReqOverTime",
    "AfterOverAdd",
    "WTID",
    "WTTypeNo",
    "WorkTime1",
    "Emp_ComeSourceName",
    "dtName4",
    "EmpName",
    "WorkTypeName",
    "WTTypeName"
]

print(f"\n📡 Fetching attendance from {START_DATE} to {END_DATE}...\n")

all_data = []

start = datetime.strptime(START_DATE, "%Y-%m-%d")
end = datetime.strptime(END_DATE, "%Y-%m-%d")

while start <= end:

    date_str = start.strftime("%Y%m%d")

    print(f"➡ Fetching {date_str}")

    payload = {
        "FunID": "KQ062001",
        "Language": 3,
        "Data": {
            "EmpNo": EMP_ID,
            "YYMMDD": date_str
        }
    }

    try:

        response = requests.post(
            BASE_URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=30
        )

        result = response.json()

        if result.get("Success"):

            data = result.get("Data", [])

            # Convert JSON string to Python object
            if isinstance(data, str):
                data = json.loads(data)

            # Handle nested structure
            if isinstance(data, dict):
                if "Table" in data:
                    data = data["Table"]
                elif "Rows" in data:
                    data = data["Rows"]
                else:
                    data = list(data.values())[0]

            # Filter required columns only
            if isinstance(data, list):

                for row in data:

                    filtered_row = {
                        col: row.get(col, "")
                        for col in REQUIRED_COLUMNS
                    }

                    all_data.append(filtered_row)

        else:
            print(f"❌ API Error : {result.get('Message')}")

    except Exception as e:
        print(f"⚠ Error : {e}")

    start += timedelta(days=1)

# ===========================
# EXPORT TO EXCEL
# ===========================

print("\n--------------------------------")
print(f"Total Records : {len(all_data)}")
print("--------------------------------")

if all_data:

    df = pd.DataFrame(all_data)

    # Keep column order exactly same
    df = df[REQUIRED_COLUMNS]

    output_file = f"attendance_{EMP_ID}.xlsx"

    df.to_excel(output_file, index=False)

    print(f"✅ Excel Created : {output_file}")

else:
    print("⚠ No attendance found.")