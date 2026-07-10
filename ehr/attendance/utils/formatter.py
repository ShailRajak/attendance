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

        formatted_data.append(formatted_row)

    return formatted_data
