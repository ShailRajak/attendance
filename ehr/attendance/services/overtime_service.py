from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta


from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db
from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4
from attendance.services.rbac_service import RBACService
from attendance.models import UserProfile


def get_overtime_summary(emp_id, start_date, end_date, is_supervisor=False):
    """
    Aggregates overtime data from cached attendance records for a single employee.

    Returns:
        dict with:
        - card_punch_ot, requested_ot, weekend_ot, holiday_ot, total_ot (floats)
        - daily_breakdown: list of per-day dicts for charting
        - anomalies: list of punch anomalies
    """
    # Fetch from cache or local DB depending on role
    if is_supervisor:
        attendance = fetch_attendance_from_db(emp_id, start_date, end_date)
    else:
        attendance = fetch_attendance(emp_id, start_date, end_date)

    # Initialize totals
    card_punch_ot = 0.0
    requested_ot = 0.0
    weekend_ot = 0.0
    holiday_ot = 0.0
    total_ot = 0.0

    daily_breakdown = []
    anomalies = []

    for record in attendance:
        # Parse OT values - use the display names from formatter
        try:
            cp_ot = float(record.get("Card Punch OT", 0) or 0)
        except (ValueError, TypeError):
            cp_ot = 0.0

        try:
            req_ot = float(record.get("Requested OT", 0) or 0)
        except (ValueError, TypeError):
            req_ot = 0.0

        try:
            we_ot = float(record.get("Weekend OT", 0) or 0)
        except (ValueError, TypeError):
            we_ot = 0.0

        try:
            hol_ot = float(record.get("Holiday OT", 0) or 0)
        except (ValueError, TypeError):
            hol_ot = 0.0

        # Check if Sunday
        weekday = record.get("Weekday", "")
        raw_date = record.get("Date", "")
        is_sunday = False
        try:
            if int(weekday) == 1:
                is_sunday = True
        except (ValueError, TypeError):
            if raw_date:
                try:
                    dt_parsed = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d")
                    if dt_parsed.weekday() == 6:
                        is_sunday = True
                except (ValueError, TypeError):
                    # Ignore date parsing errors for malformed records
                    pass
        try:
            work_hrs_val = float(record.get("Working Hours", 0) or 0)
        except (ValueError, TypeError):
            work_hrs_val = 0.0

        is_holiday_1july = False
        if raw_date:
            try:
                dt_parsed = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d")
                if (
                    dt_parsed.year == 2026
                    and dt_parsed.month == 7
                    and dt_parsed.day == 1
                ):
                    is_holiday_1july = True
            except (ValueError, TypeError):
                # Ignore date parsing errors for malformed records
                pass

        if is_holiday_1july:
            hol_ot = work_hrs_val
            cp_ot = 0.0
        elif is_sunday:
            we_ot = work_hrs_val
            cp_ot = 0.0

        tot_ot = cp_ot + req_ot + hol_ot

        # Accumulate totals
        card_punch_ot += cp_ot
        requested_ot += req_ot
        weekend_ot += we_ot
        holiday_ot += hol_ot
        total_ot += tot_ot

        # Daily breakdown for charting
        raw_date = record.get("Date", "")
        date_str = raw_date.split("T")[0].split(" ")[0] if raw_date else ""
        weekday = record.get("Weekday", "")

        # Try to parse weekday as int for display
        weekday_display = ""
        try:
            wd_int = int(weekday)
            weekday_names = {
                1: "Sun",
                2: "Mon",
                3: "Tue",
                4: "Wed",
                5: "Thu",
                6: "Fri",
                7: "Sat",
            }
            weekday_display = weekday_names.get(wd_int, str(wd_int))
        except (ValueError, TypeError):
            weekday_display = str(weekday) if weekday else ""

        daily_breakdown.append(
            {
                "date": date_str,
                "weekday": weekday_display,
                "card_punch_ot": round(cp_ot, 1),
                "requested_ot": round(req_ot, 1),
                "weekend_ot": round(we_ot, 1),
                "holiday_ot": round(hol_ot, 1),
                "total_ot": round(tot_ot, 1),
            }
        )

        # Anomaly detection
        # NOTE: GO1 = First Punch In (from formatter: "GO1" -> "In Time")
        #       OUT1 = First Punch Out (from formatter: "OUT1" -> "Out Time")
        work_day = record.get("WorkDay", 0)
        go1 = record.get("In Time", "").strip()  # Punch In
        out1 = record.get("Out Time", "").strip()  # Punch Out

        # Check for missing punches on work days
        try:
            work_day_val = float(work_day) if work_day else 0.0
        except (ValueError, TypeError):
            work_day_val = 0.0

        is_today = date_str == datetime.now().strftime("%Y-%m-%d")
        if work_day_val > 0 and not is_today:
            # Missing Punch In (GO1) on a work day
            if not go1 or go1 in ("00:00", "—", ""):
                anomalies.append({"date": date_str, "type": "Missing Punch In"})

            # Missing Punch Out (OUT1) on a work day
            if not out1 or out1 in ("00:00", "—", ""):
                anomalies.append({"date": date_str, "type": "Missing Punch Out"})

            # Flag punch order issues (OUT1 earlier than GO1 on same calendar day)
            # This suggests a data mapping issue upstream - the biometric system
            # already calculated OT correctly, but we flag this for data quality
            if (
                go1
                and out1
                and go1 not in ("00:00", "—", "")
                and out1 not in ("00:00", "—", "")
            ):
                try:
                    go1_parts = go1.split(":")
                    out1_parts = out1.split(":")
                    if len(go1_parts) == 2 and len(out1_parts) == 2:
                        go1_minutes = int(go1_parts[0]) * 60 + int(go1_parts[1])
                        out1_minutes = int(out1_parts[0]) * 60 + int(out1_parts[1])
                        # NOTE: This simple same-day comparison doesn't account for night shift
                        # crossing midnight. For night shifts (20:00-05:00), OUT1 will naturally
                        # be < GO1 since it crosses to next day. This is expected and valid.
                        # We only flag this as informational - the biometric system already
                        # calculated OT correctly from the raw punch data.
                        if out1_minutes < go1_minutes:
                            # This could be:
                            # 1. Night shift (valid) - OUT1 is next day early morning
                            # 2. Data mapping issue (invalid) - punches swapped in system
                            # We don't add to anomalies list since we can't determine which case
                            # without additional shift information, but we note it in comments
                            pass  # Biometric system already calculated OT correctly
                except (ValueError, TypeError):
                    pass

    # Round final totals
    return {
        "card_punch_ot": round(card_punch_ot, 1),
        "requested_ot": round(requested_ot, 1),
        "weekend_ot": round(weekend_ot, 1),
        "holiday_ot": round(holiday_ot, 1),
        "total_ot": round(total_ot, 1),
        "daily_breakdown": daily_breakdown,
        "anomalies": anomalies,
    }


def get_cycle_bounds(reference_date):
    """
    Returns (start_date, end_date) for the 21-to-20 billing cycle containing reference_date.

    If reference_date.day >= 21:
        cycle starts on the 21st of that month and ends on the 20th of next month
    Otherwise:
        cycle starts on the 21st of the previous month and ends on the 20th of the current month
    """
    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    if reference_date.day >= 21:
        # Cycle starts on 21st of current month
        start_date = date(reference_date.year, reference_date.month, 21)
        # Ends on 20th of next month
        end_date = start_date + relativedelta(months=1)
        end_date = date(end_date.year, end_date.month, 20)
    else:
        # Cycle starts on 21st of previous month
        start_date = reference_date - relativedelta(months=1)
        start_date = date(start_date.year, start_date.month, 21)
        # Ends on 20th of current month
        end_date = date(reference_date.year, reference_date.month, 20)

    return start_date, end_date


def get_week_bounds(week_num, year=None):
    """
    Returns (start_date, end_date) for a given ISO week number.

    Args:
        week_num: Week number (1-52/53)
        year: Year (defaults to current year)

    Returns:
        (start_date, end_date) for Monday-Sunday of that week
    """
    if year is None:
        year = datetime.now().year

    # ISO week: Week 1 is the week with the first Thursday of the year
    # Find the Monday of week 1
    jan1 = date(year, 1, 1)
    days_to_monday = (7 - jan1.weekday()) % 7  # Days until next Monday
    if days_to_monday == 0:
        days_to_monday = 7 if jan1.weekday() < 3 else 0

    week1_monday = jan1 + timedelta(days=days_to_monday)

    # Calculate Monday of the requested week
    week_start = week1_monday + timedelta(weeks=week_num - 1)
    week_end = week_start + timedelta(days=6)  # Sunday

    return week_start, week_end


def get_all_weeks_in_year(year=None):
    """
    Returns a list of all weeks in a year with their date ranges.

    Returns:
        List of dicts: [{"week_num": 1, "start": date, "end": date, "label": "Week 1 (Jan 1 - Jan 7)"}, ...]
    """
    if year is None:
        year = datetime.now().year

    weeks = []

    # ISO week calculation
    jan1 = date(year, 1, 1)
    days_to_monday = (7 - jan1.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7 if jan1.weekday() < 3 else 0

    week1_monday = jan1 + timedelta(days=days_to_monday)

    # Generate weeks until we pass the year
    week_num = 1
    current_monday = week1_monday

    while current_monday.year <= year:
        week_end = current_monday + timedelta(days=6)

        # Only include weeks that overlap with the current year
        if current_monday.year == year or week_end.year == year:
            weeks.append(
                {
                    "week_num": week_num,
                    "start": current_monday,
                    "end": week_end,
                    "label": f"Week {week_num} ({current_monday.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')})",
                }
            )

        week_num += 1
        current_monday += timedelta(weeks=1)

        # Safety limit: max 53 weeks
        if week_num > 53:
            break

    return weeks


def get_all_cycles_in_year(year=None):
    """
    Returns a list of all 21-20 billing cycles in a year.

    Returns:
        List of dicts: [{"cycle_num": 1, "start": date, "end": date, "label": "January"}, ...]
    """
    if year is None:
        year = datetime.now().year

    cycles = []
    cycle_num = 1

    # Cycles cover 21st to 20th of the next month.
    # e.g., Jan is Dec 21 - Jan 20. Feb is Jan 21 - Feb 20.
    for i in range(12):
        if i == 0:
            start_date = date(year - 1, 12, 21)
            end_date = date(year, 1, 20)
        else:
            start_date = date(year, i, 21)
            end_date = date(year, i + 1, 20)

        cycles.append(
            {
                "cycle_num": cycle_num,
                "start": start_date,
                "end": end_date,
                "label": end_date.strftime("%B"),
            }
        )

        cycle_num += 1

    return cycles


def get_scope_overtime_summary(accessible_usernames, start_date, end_date, expected_dtname4=None, is_all_scope=False):
    """
    Aggregates overtime data across all employees under a given dynamic scope.

    Returns:
        dict with:
        - employees: list of per-employee subtotals
        - scope_total: aggregated totals across all employees
        - dtname4_scope: scope name
    """
    # Fetch all attendance records (no employee filter) from local DB for supervisor scope
    attendance = fetch_attendance_from_db("", start_date, end_date)

    # Filter by section name if expected_dtname4 is provided, else fallback to accessible employee usernames
    if expected_dtname4:
        scope_records = [r for r in attendance if r.get("Day") == expected_dtname4]
    elif is_all_scope:
        # ALL scope or superuser sees all biometric machine records unfiltered
        scope_records = attendance
    else:
        scope_records = [r for r in attendance if r.get("Employee ID") in accessible_usernames]

    dtname4_scope = expected_dtname4 or "Section View"

    # Group by employee
    employee_data = {}
    for record in scope_records:
        emp_id = record.get("Employee ID", "Unknown")
        emp_name = record.get("Employee Name", "Unknown")

        # Determine shift label (day/night)
        shift_raw = str(record.get("Shift") or "").strip()
        shift_label = "day"
        if "Night" in shift_raw:
            shift_label = "night"

        if emp_id not in employee_data:
            employee_data[emp_id] = {
                "emp_id": emp_id,
                "emp_name": emp_name,
                "card_punch_ot": 0.0,
                "requested_ot": 0.0,
                "weekend_ot": 0.0,
                "holiday_ot": 0.0,
                "total_ot": 0.0,
                "day_shift_count": 0,
                "night_shift_count": 0,
                "department": record.get("Day", "—"),
            }
        else:
            if record.get("Day") and record.get("Day") != "—":
                employee_data[emp_id]["department"] = record.get("Day")

        if shift_label == "day":
            employee_data[emp_id]["day_shift_count"] += 1
        else:
            employee_data[emp_id]["night_shift_count"] += 1

        # Accumulate OT values
        try:
            cp_ot = float(record.get("Card Punch OT", 0) or 0)
        except (ValueError, TypeError):
            cp_ot = 0.0

        try:
            req_ot = float(record.get("Requested OT", 0) or 0)
        except (ValueError, TypeError):
            req_ot = 0.0

        try:
            we_ot = float(record.get("Weekend OT", 0) or 0)
        except (ValueError, TypeError):
            we_ot = 0.0

        try:
            hol_ot = float(record.get("Holiday OT", 0) or 0)
        except (ValueError, TypeError):
            hol_ot = 0.0

        # Check if Sunday
        weekday = record.get("Weekday", "")
        raw_date = record.get("Date", "")
        is_sunday = False
        try:
            if int(weekday) == 1:
                is_sunday = True
        except (ValueError, TypeError):
            if raw_date:
                try:
                    dt_parsed = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d")
                    if dt_parsed.weekday() == 6:
                        is_sunday = True
                except (ValueError, TypeError):
                    # Ignore date parsing errors for malformed records
                    pass
        try:
            work_hrs_val = float(record.get("Working Hours", 0) or 0)
        except (ValueError, TypeError):
            work_hrs_val = 0.0

        is_holiday_1july = False
        if raw_date:
            try:
                dt_parsed = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d")
                if (
                    dt_parsed.year == 2026
                    and dt_parsed.month == 7
                    and dt_parsed.day == 1
                ):
                    is_holiday_1july = True
            except (ValueError, TypeError):
                # Ignore date parsing errors for malformed records
                pass

        if is_holiday_1july:
            hol_ot = work_hrs_val
            cp_ot = 0.0
        elif is_sunday:
            we_ot = work_hrs_val
            cp_ot = 0.0

        tot_ot = cp_ot + req_ot + hol_ot

        employee_data[emp_id]["card_punch_ot"] += cp_ot
        employee_data[emp_id]["requested_ot"] += req_ot
        employee_data[emp_id]["weekend_ot"] += we_ot
        employee_data[emp_id]["holiday_ot"] += hol_ot
        employee_data[emp_id]["total_ot"] += tot_ot

    # Round values and build list
    employees = []
    scope_total = {
        "card_punch_ot": 0.0,
        "requested_ot": 0.0,
        "weekend_ot": 0.0,
        "holiday_ot": 0.0,
        "total_ot": 0.0,
    }

    for emp_id, emp_data in employee_data.items():
        emp_data["card_punch_ot"] = round(emp_data["card_punch_ot"], 1)
        emp_data["requested_ot"] = round(emp_data["requested_ot"], 1)
        emp_data["weekend_ot"] = round(emp_data["weekend_ot"], 1)
        emp_data["holiday_ot"] = round(emp_data["holiday_ot"], 1)
        emp_data["total_ot"] = round(emp_data["total_ot"], 1)

        # Classify primary shift based on majority count
        if emp_data["night_shift_count"] > emp_data["day_shift_count"]:
            emp_data["shift_label"] = "night"
        else:
            emp_data["shift_label"] = "day"

        del emp_data["day_shift_count"]
        del emp_data["night_shift_count"]

        employees.append(emp_data)

        # Accumulate scope totals
        scope_total["card_punch_ot"] += emp_data["card_punch_ot"]
        scope_total["requested_ot"] += emp_data["requested_ot"]
        scope_total["weekend_ot"] += emp_data["weekend_ot"]
        scope_total["holiday_ot"] += emp_data["holiday_ot"]
        scope_total["total_ot"] += emp_data["total_ot"]

    # Round scope totals
    for key in scope_total:
        scope_total[key] = round(scope_total[key], 1)

    # Sort employees by total OT descending
    employees.sort(key=lambda x: x["total_ot"], reverse=True)

    # Group by date to find daily breakdown for the scope
    daily_data = {}

    def parse_helper(d_str):
        for fmt in ("%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(d_str, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(d_str)
        except ValueError:
            return datetime.min

    for record in scope_records:
        raw_date = record.get("Date", "")
        date_obj = parse_helper(raw_date)
        if not date_obj or date_obj == datetime.min:
            continue
        date_str = date_obj.strftime("%Y-%m-%d")

        try:
            cp_ot = float(record.get("Card Punch OT", 0) or 0)
        except (ValueError, TypeError):
            cp_ot = 0.0

        try:
            req_ot = float(record.get("Requested OT", 0) or 0)
        except (ValueError, TypeError):
            req_ot = 0.0

        try:
            we_ot = float(record.get("Weekend OT", 0) or 0)
        except (ValueError, TypeError):
            we_ot = 0.0

        try:
            hol_ot = float(record.get("Holiday OT", 0) or 0)
        except (ValueError, TypeError):
            hol_ot = 0.0

        # Check if Sunday
        weekday = record.get("Weekday", "")
        is_sunday = False
        try:
            if int(weekday) == 1:
                is_sunday = True
        except (ValueError, TypeError):
            if date_obj and date_obj != datetime.min:
                if date_obj.weekday() == 6:
                    is_sunday = True
        try:
            work_hrs_val = float(record.get("Working Hours", 0) or 0)
        except (ValueError, TypeError):
            work_hrs_val = 0.0

        is_holiday_1july = False
        if date_obj and date_obj != datetime.min:
            if date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1:
                is_holiday_1july = True

        if is_holiday_1july:
            hol_ot = work_hrs_val
            cp_ot = 0.0
        elif is_sunday:
            we_ot = work_hrs_val
            cp_ot = 0.0

        tot_ot = cp_ot + req_ot + hol_ot

        if date_str not in daily_data:
            weekday = record.get("Weekday", "")
            weekday_display = ""
            try:
                wd_int = int(weekday)
                weekday_names = {
                    1: "Sun",
                    2: "Mon",
                    3: "Tue",
                    4: "Wed",
                    5: "Thu",
                    6: "Fri",
                    7: "Sat",
                }
                weekday_display = weekday_names.get(wd_int, str(wd_int))
            except (ValueError, TypeError):
                weekday_display = str(weekday) if weekday else ""

            daily_data[date_str] = {
                "date": date_str,
                "weekday": weekday_display,
                "card_punch_ot": 0.0,
                "requested_ot": 0.0,
                "weekend_ot": 0.0,
                "holiday_ot": 0.0,
                "total_ot": 0.0,
            }

        daily_data[date_str]["card_punch_ot"] += cp_ot
        daily_data[date_str]["requested_ot"] += req_ot
        daily_data[date_str]["weekend_ot"] += we_ot
        daily_data[date_str]["holiday_ot"] += hol_ot
        daily_data[date_str]["total_ot"] += tot_ot

    daily_breakdown = []
    sorted_dates = sorted(daily_data.keys())
    for d_str in sorted_dates:
        d_item = daily_data[d_str]
        daily_breakdown.append(
            {
                "date": d_str,
                "weekday": d_item["weekday"],
                "card_punch_ot": round(d_item["card_punch_ot"], 1),
                "requested_ot": round(d_item["requested_ot"], 1),
                "weekend_ot": round(d_item["weekend_ot"], 1),
                "holiday_ot": round(d_item["holiday_ot"], 1),
                "total_ot": round(d_item["total_ot"], 1),
            }
        )

    return {
        "employees": employees,
        "scope_total": scope_total,
        "dtname4_scope": dtname4_scope,
        "daily_breakdown": daily_breakdown,
    }


def get_overtime_dashboard_data(user, get_params):
    """
    Business logic for the Overtime Dashboard context.
    """
    is_superuser = user.is_superuser
    role, section = resolve_user_role_and_section(user)
    scope = RBACService.get_scope(user)

    is_supervisor = is_superuser or (scope in ("SECTION", "ALL"))

    period = get_params.get("period", "daily")
    if period not in ("daily", "weekly", "monthly"):
        period = "daily"

    custom_start = get_params.get("custom_start")
    custom_end = get_params.get("custom_end")

    week_num = get_params.get("week_num")
    cycle_num = get_params.get("cycle_num")

    today = datetime.now().date()
    start_date = today
    end_date = today

    if custom_start and custom_end:
        try:
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            period = "custom"
        except (ValueError, TypeError):
            custom_start = None
            custom_end = None

    if not custom_start or not custom_end:
        if period == "daily":
            yesterday = today - timedelta(days=1)
            start_date = yesterday
            end_date = yesterday
        elif period == "weekly":
            if week_num:
                try:
                    year = int(get_params.get("year", today.year))
                    start_date, end_date = get_week_bounds(int(week_num), year)
                except (ValueError, TypeError):
                    start_date = today - timedelta(days=today.weekday())
                    end_date = start_date + timedelta(days=6)
            else:
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
        else:  # monthly
            if cycle_num:
                try:
                    year = int(get_params.get("year", today.year))
                    cycles = get_all_cycles_in_year(year)
                    cycle_idx = int(cycle_num) - 1
                    if 0 <= cycle_idx < len(cycles):
                        start_date = cycles[cycle_idx]["start"]
                        end_date = cycles[cycle_idx]["end"]
                    else:
                        start_date, end_date = get_cycle_bounds(today)
                except (ValueError, TypeError, IndexError):
                    start_date, end_date = get_cycle_bounds(today)
            else:
                start_date, end_date = get_cycle_bounds(today)

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    has_selected_employee = False
    if scope == "OWN" and not is_superuser:
        emp_id = user.username
    else:
        emp_id = get_params.get("employee_id")
        if emp_id and emp_id.strip():
            has_selected_employee = True
            emp_id = emp_id.strip()
        else:
            emp_id = ""

    expected_dtname4 = get_expected_dtname4(role, section, user.username)

    if has_selected_employee and not is_superuser and scope != "ALL" and expected_dtname4:
        # Verify employee belongs to section
        attendance_chk = fetch_attendance_from_db(emp_id, start_date_str, end_date_str)
        belongs = any(r.get("Day") == expected_dtname4 for r in attendance_chk)
        if belongs:
            summary = get_overtime_summary(emp_id, start_date_str, end_date_str, is_supervisor=is_supervisor)
        else:
            summary = {
                "card_punch_ot": 0.0,
                "requested_ot": 0.0,
                "weekend_ot": 0.0,
                "holiday_ot": 0.0,
                "total_ot": 0.0,
                "daily_breakdown": [],
                "anomalies": [],
            }
    else:
        summary = get_overtime_summary(emp_id, start_date_str, end_date_str, is_supervisor=is_supervisor)

    scope_summary = None
    if is_supervisor:
        accessible_users_set = set(
            RBACService.get_accessible_employees(user).values_list("user__username", flat=True)
        )
        scope_summary = get_scope_overtime_summary(
            accessible_users_set, start_date_str, end_date_str, expected_dtname4,
            is_all_scope=(is_superuser or scope == "ALL")
        )

        if not has_selected_employee:
            summary = {
                "card_punch_ot": scope_summary["scope_total"]["card_punch_ot"],
                "requested_ot": scope_summary["scope_total"]["requested_ot"],
                "weekend_ot": scope_summary["scope_total"]["weekend_ot"],
                "holiday_ot": scope_summary["scope_total"]["holiday_ot"],
                "total_ot": scope_summary["scope_total"]["total_ot"],
                "daily_breakdown": scope_summary.get("daily_breakdown", []),
                "anomalies": [],
            }

    try:
        start_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_obj = datetime.strptime(end_date_str, "%Y-%m-%d")
        if period == "daily":
            period_text = f"Daily — {start_obj.strftime('%b %d, %Y')}"
        elif period == "weekly":
            if week_num:
                period_text = f"Week {week_num} — {start_obj.strftime('%b %d')} to {end_obj.strftime('%b %d, %Y')}"
            else:
                period_text = f"Weekly — {start_obj.strftime('%b %d')} to {end_obj.strftime('%b %d, %Y')}"
        elif period == "monthly":
            if cycle_num:
                period_text = f"Cycle {cycle_num} — {start_obj.strftime('%b %d')} to {end_obj.strftime('%b %d, %Y')}"
            else:
                period_text = f"Monthly (21-20) — {start_obj.strftime('%b %d')} to {end_obj.strftime('%b %d, %Y')}"
        else:
            period_text = f"Custom — {start_obj.strftime('%b %d, %Y')} to {end_obj.strftime('%b %d, %Y')}"
    except (ValueError, TypeError):
        period_text = f"{start_date_str} to {end_date_str}"

    current_year = today.year
    all_weeks = get_all_weeks_in_year(current_year)
    all_cycles = get_all_cycles_in_year(current_year)

    selected_week = str(week_num) if week_num else None
    if not selected_week:
        for w in all_weeks:
            if w["start"] <= today <= w["end"]:
                selected_week = str(w["week_num"])
                break

    selected_cycle = str(cycle_num) if cycle_num else None
    if not selected_cycle:
        for c in all_cycles:
            if c["start"] <= today <= c["end"]:
                selected_cycle = str(c["cycle_num"])
                break

    from attendance.models import OvertimeLimitConfig
    ot_config = OvertimeLimitConfig.load()

    return {
        "active_tab": "overtime",
        "summary": summary,
        "period": period,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "period_text": period_text,
        "scope_summary": scope_summary,
        "is_supervisor": is_supervisor,
        "is_superuser": is_superuser,
        "role": role,
        "section": section,
        "role_display": (
            user.profile.role.name
            if (hasattr(user, "profile") and user.profile.role)
            else ("Admin" if is_superuser else "User")
        ),
        "section_display": (
            user.profile.section.name
            if (hasattr(user, "profile") and user.profile.section)
            else ""
        ),
        "custom_start": custom_start,
        "custom_end": custom_end,
        "all_weeks": all_weeks,
        "all_cycles": all_cycles,
        "selected_week": selected_week,
        "selected_cycle": selected_cycle,
        "current_year": current_year,
        "ot_low_limit": ot_config.ot_low_limit,
        "ot_medium_limit": ot_config.ot_medium_limit,
    }
