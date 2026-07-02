import requests
import json
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "http://10.61.248.6:18010/RESTService/Search"

EMP_ID = "19105203"   # ✅ FIXED (REAL EmpID)

START_DATE = "2026-03-21"
END_DATE = "2026-04-20"

headers = {"Content-Type": "text"}

print(f"\n📡 Fetching attendance from {START_DATE} to {END_DATE}...")

all_data = []

start = datetime.strptime(START_DATE, "%Y-%m-%d")
end = datetime.strptime(END_DATE, "%Y-%m-%d")

while start <= end:
    date_str = start.strftime("%Y%m%d")

    print(f"➡️ Fetching {date_str}...")

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

            # Fix structure
            if isinstance(data, str):
                data = json.loads(data)

            if isinstance(data, dict):
                data = data.get("Table") or data.get("Rows") or list(data.values())[0]

            if data:
                all_data.extend(data)

        else:
            print(f"❌ API Error on {date_str}: {result.get('Message')}")

    except Exception as e:
        print(f"⚠️ Error on {date_str}: {e}")

    start += timedelta(days=1)

# ==============================
# EXPORT
# ==============================
print(f"\n✅ Total rows collected: {len(all_data)}")

if all_data:
    df = pd.DataFrame(all_data)
    file_name = f"attendance_{EMP_ID}.xlsx"
    df.to_excel(file_name, index=False)

    print(f"💾 Excel created: {file_name}")
else:
    print("⚠️ No data found")