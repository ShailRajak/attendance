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
        else:
            return 0.0
    else:
        shift_end_mins = 18 * 60
        if out_mins > shift_end_mins:
            ot_mins = out_mins - shift_end_mins
        else:
            return 0.0

    if ot_mins < 15:
        return 0.0

    # OT Rounding Policy:
    # 20 mins past shift end (e.g. 18:20) -> 0.5h
    # 50 mins past shift end (e.g. 18:50) -> 1.0h
    # 80 mins (1h 20m) past shift end (e.g. 19:20) -> 1.5h
    blocks = (ot_mins + 10) // 30
    return round(blocks * 0.5, 1)


class AttendanceStatus:
    FULL_DAY = "Full Day"
    HALF_DAY = "Half Day"
    SHORT_LEAVE = "Short Leave"
    MISPUNCH = "Mispunch"
    ABSENT = "Absent"
    APPROVED_LEAVE = "Approved Leave"
    HOLIDAY = "Holiday"
    WEEKLY_OFF = "Weekly Off"
    REST_DAY = "Rest Day"

    PRESENT_SET = {FULL_DAY, HALF_DAY, SHORT_LEAVE, MISPUNCH}


def parse_shift_times(shift_name=""):
    """
    Dynamically extracts shift start and end times in minutes from shift string.
    Returns tuple (shift_start_mins, shift_end_mins, allowed_exit_mins, shift_midpoint_mins).
    10-minute early exit relaxation rule: Allowed Exit Time = Shift End Time - 10 Minutes.
    """
    import re
    shift_str = str(shift_name or "").strip()
    match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", shift_str)
    if match:
        sh, sm, eh, em = map(int, match.groups())
        shift_start = sh * 60 + sm
        shift_end = eh * 60 + em
    elif "Night" in shift_str or "NS" in shift_str:
        shift_start = 20 * 60  # 20:00
        shift_end = 8 * 60     # 08:00
    else:
        shift_start = 9 * 60   # 09:00
        shift_end = 18 * 60    # 18:00

    allowed_exit = shift_end - 10
    shift_midpoint = shift_start + (shift_end - shift_start) // 2
    return shift_start, shift_end, allowed_exit, shift_midpoint


def classify_attendance(record, monthly_late_count=None):
    """
    Centralized Attendance Classification Engine.
    Single source of truth for all modules and roles in HRMS.

    Classification Priority Order (stops immediately on first match):
    1. Holiday
    2. Weekly Off
    3. Rest Day
    4. Approved Leave
    5. Absent (Both punches missing)
    6. Mispunch (Exactly one punch missing)
    7. Full Day (Both punches exist, Working Hours >= 8.0 AND exit >= Shift End - 10 Mins AND Late <= 60m within 3 allowed monthly late logins)
    8. Short Leave (Both punches exist, misses up to 2 Hours from shift start or end)
    9. Half Day (Both punches exist, 4.0 <= Working Hours < 8.0 OR 4th+ late login)
    10. Fallback: Any other punched record
    """
    in_time = str(record.get("In Time") or record.get("in_time") or record.get("GO1") or "").strip()
    out_time = str(record.get("Out Time") or record.get("out_time") or record.get("OUT1") or "").strip()
    leave_type = str(record.get("Leave Type") or record.get("leave_type") or record.get("LeaveTypeName") or "").strip()
    shift_name = str(record.get("Shift") or record.get("shift_name") or record.get("WTTypeName") or "").strip()
    raw_status = str(record.get("Attendance Status") or record.get("status") or record.get("WorkTypeName") or "").strip()
    date_val = record.get("Date") or record.get("raw_date") or record.get("YYMMDD") or ""

    if in_time in ("00:00", "—", "None", "0"):
        in_time = ""
    if out_time in ("00:00", "—", "None", "0"):
        out_time = ""
    if leave_type in ("None", "0", "—", ""):
        leave_type = ""

    has_in = bool(in_time)
    has_out = bool(out_time)

    try:
        work_hrs = float(record.get("Working Hours") or record.get("work_hrs") or record.get("WorkTime1") or 0.0)
    except (ValueError, TypeError):
        work_hrs = 0.0

    date_obj = None
    if isinstance(date_val, datetime):
        date_obj = date_val.date()
    elif isinstance(date_val, str) and date_val.strip():
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                date_obj = datetime.strptime(date_val.strip(), fmt).date()
                break
            except ValueError:
                pass

    is_sunday = (date_obj.weekday() == 6) if date_obj else False
    is_holiday_date = (date_obj and date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1)
    try:
        holiday_ot = float(record.get("Holiday OT") or record.get("OverTime3") or 0.0)
    except (ValueError, TypeError):
        holiday_ot = 0.0

    # Priority 1: Holiday
    if raw_status == "Holiday" or is_holiday_date or holiday_ot > 0:
        if not has_in and not has_out:
            return AttendanceStatus.HOLIDAY

    # Priority 2: Weekly Off
    if is_sunday or raw_status == "Weekly Off":
        if not has_in and not has_out:
            return AttendanceStatus.WEEKLY_OFF

    # Priority 3: Rest Day
    if raw_status == "Rest Day":
        if not has_in and not has_out:
            return AttendanceStatus.REST_DAY

    # Priority 4: Approved Leave
    if leave_type:
        return AttendanceStatus.APPROVED_LEAVE

    # Priority 5: Absent (Both punches missing)
    if not has_in and not has_out:
        return AttendanceStatus.ABSENT

    # Priority 6: Mispunch (Exactly one punch missing)
    if (has_in and not has_out) or (has_out and not has_in):
        return AttendanceStatus.MISPUNCH

    # Both IN and OUT punches exist
    shift_start, shift_end, allowed_exit, shift_midpoint = parse_shift_times(shift_name)

    def to_mins(t_str):
        try:
            h, m = map(int, t_str.split(":"))
            return h * 60 + m
        except (ValueError, TypeError, AttributeError):
            return 0

    actual_in = to_mins(in_time)
    actual_out = to_mins(out_time)

    late_mins = actual_in - shift_start if actual_in >= shift_start else 0
    early_mins = shift_end - actual_out if shift_end >= actual_out else 0

    # Retrieve monthly late login index
    late_idx = record.get("monthly_late_count") or record.get("late_count_in_month") or monthly_late_count or 1

    # 4th+ late login in calendar month (0 < late_mins <= 60) -> Half Day
    if 0 < late_mins <= 60 and late_idx >= 4:
        return AttendanceStatus.HALF_DAY

    # Priority 7: Full Day
    is_valid_late_relaxation = (late_mins <= 15) or (0 < late_mins <= 60 and late_idx <= 3)
    is_full_day = (work_hrs >= 8.0) and (actual_out >= allowed_exit) and is_valid_late_relaxation
    if is_full_day:
        return AttendanceStatus.FULL_DAY

    # Priority 8: Short Leave
    is_short_leave = (late_mins <= 120 and early_mins <= 120) and ((0 < late_mins <= 120) or (0 < early_mins <= 120))
    if is_short_leave and work_hrs >= 5.0:
        return AttendanceStatus.SHORT_LEAVE

    # Priority 9: Half Day
    is_first_half = (actual_in <= shift_start + 30) and (actual_out >= shift_midpoint - 30)
    is_second_half = (actual_in <= shift_midpoint + 30) and (actual_out >= allowed_exit)

    if (4.0 <= work_hrs < 8.0) and (is_first_half or is_second_half):
        return AttendanceStatus.HALF_DAY

    # Fallback for punched records
    if work_hrs >= 5.5:
        return AttendanceStatus.SHORT_LEAVE
    elif work_hrs >= 4.0:
        return AttendanceStatus.HALF_DAY

    return AttendanceStatus.HALF_DAY


def is_present_status(status):
    """
    Formula: Present = Full Day + Half Day + Short Leave + Mispunch
    Excludes: Approved Leave, Holiday, Weekly Off, Rest Day, Absent
    """
    return status in AttendanceStatus.PRESENT_SET or status == "Present"


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
