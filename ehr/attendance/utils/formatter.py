from datetime import datetime

# ==========================================================
# REQUIRED COLUMNS
# ==========================================================

REQUIRED_COLUMNS = {
    "YYMMDD": "Date",
    "EmpNo": "Employee ID",
    "EmpName": "Employee Name",
    "GO1": "In Time",
    "OUT1": "Out Time",
    "WorkTime1": "Working Hours",
    "WorkTime": "Work Time",
    "OverTime": "Card Punch OT",
    "OverTime1": "Requested OT",
    "OverTime2": "Weekend OT",
    "OverTime3": "Holiday OT",
    "OverTime4": "OT4",
    "OverTimeAll": "Total OT All",
    "ReqOverTime": "Req OverTime",
    "AfterOverAdd": "Approved OT",
    "WTID": "WT ID",
    "WTTypeNo": "WT Type No",
    "Emp_ComeSourceName": "Attendance Source",
    "dtName4": "Day",
    "WorkTypeName": "Attendance Status",
    "WTTypeName": "Shift",
    "Mobile": "Mobile",
    "LaterMin1": "Late Minutes",
    "LeaveTypeName": "Leave Type",
    "WorkDay": "WorkDay",
    "Weekday": "Weekday",
}


# ==========================================================
# DATE FORMAT
# ==========================================================


def format_date(date_value):
    """
    Convert
    20260321

    into

    21-03-2026
    """

    if not date_value:
        return ""

    try:
        return datetime.strptime(str(date_value), "%Y%m%d").strftime("%d-%m-%Y")

    except (ValueError, TypeError):
        return str(date_value)


# ==========================================================
# TIME FORMAT
# ==========================================================


def format_time(time_value):
    """
    Handles values like

    0901
    901
    09:01

    Returns

    09:01
    """

    if time_value in (None, "", "0"):
        return ""

    value = str(time_value).replace(":", "").zfill(4)

    if len(value) != 4:
        return str(time_value)

    return f"{value[:2]}:{value[2:]}"


def calculate_validated_ot(out_time, shift_name="", raw_ot=0.0):
    """
    Validates and calculates Overtime (OT).
    OT is ONLY counted if the employee worked past their respective shift end time.
    - Day Shift / General Shift: Shift End is 18:00 (6:00 PM).
    - Night Shift: Shift End is 08:00 (8:00 AM).
    If check-out time is before or at shift end time, OT is strictly 0.0.
    If check-out time is after shift end time, OT is calculated as time worked after shift end.
    """
    if not out_time or str(out_time).strip() in ("00:00", "—", "", "None"):
        return 0.0

    out_str = str(out_time).strip()
    if ":" not in out_str:
        return 0.0

    try:
        parts = out_str.split(":")
        out_mins = int(parts[0]) * 60 + int(parts[1])
    except (ValueError, TypeError):
        return 0.0

    shift_str = str(shift_name or "").strip()
    is_night = "Night" in shift_str

    if is_night:
        shift_end_mins = 8 * 60
        if out_mins > shift_end_mins and out_mins < 12 * 60:
            ot_mins = out_mins - shift_end_mins
            return round(ot_mins / 60.0, 1)
        else:
            return 0.0
    else:
        shift_end_mins = 18 * 60
        if out_mins > shift_end_mins:
            ot_mins = out_mins - shift_end_mins
            return round(ot_mins / 60.0, 1)
        else:
            return 0.0


def is_full_day_present(work_time, out_time="", shift_name="", is_today=False):
    """
    Checks if an attendance record qualifies for full-day Present status with 10-minute relaxation.
    - Day Shift (09:00 - 18:00):
      Relaxed check-out threshold is 17:50 (5:50 PM).
      If check-out >= 17:50 (or work_time >= 7.8 hours), it counts as full day Present.
    - Night Shift (20:00 - 08:00):
      Relaxed check-out threshold is 07:50 AM.
      If check-out >= 07:50 AM (or work_time >= 11.8 hours), it counts as full day Present.
    - Minimum working hours threshold with 10-minute relaxation: 7.8 hours (7h 50m).
    """
    if is_today:
        return True

    try:
        wt = float(work_time or 0.0)
    except (ValueError, TypeError):
        wt = 0.0

    if wt >= 7.8:
        return True

    if out_time and str(out_time).strip() not in ("00:00", "—", "", "None"):
        out_str = str(out_time).strip()
        if ":" in out_str:
            try:
                parts = out_str.split(":")
                out_mins = int(parts[0]) * 60 + int(parts[1])
                is_night = "Night" in str(shift_name or "")
                if is_night:
                    if 470 <= out_mins < 12 * 60:
                        return True
                else:
                    if out_mins >= 1070:
                        return True
            except (ValueError, TypeError):
                pass

    return False


# ==========================================================
# MAIN FORMATTER
# ==========================================================


def filter_attendance_data(records):
    """
    Filters API response and keeps only required fields.
    """

    formatted_data = []

    for row in records:

        formatted_row = {}

        for api_column, display_name in REQUIRED_COLUMNS.items():

            value = row.get(api_column, "")

            # Format Date
            if api_column == "YYMMDD":
                value = format_date(value)

            # Format Time
            elif api_column in ["GO1", "OUT1"]:
                value = format_time(value)

            # Replace None
            elif value is None:
                value = ""

            formatted_row[display_name] = value

        # Validate Card Punch OT: Only count OT if employee worked after shift end!
        out_val = formatted_row.get("Out Time", "")
        shift_val = formatted_row.get("Shift", "")
        raw_ot_val = formatted_row.get("Card Punch OT", 0.0)
        formatted_row["Card Punch OT"] = calculate_validated_ot(out_val, shift_val, raw_ot_val)

        formatted_data.append(formatted_row)

    return formatted_data
