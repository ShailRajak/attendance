from datetime import datetime, timedelta
import re

from attendance.models import UserProfile
from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4
from attendance.services.rbac_service import RBACService
from attendance.services.attendance_service import fetch_attendance
from attendance.services.analytics_service import parse_date
from attendance.services.overtime_service import (
    get_all_cycles_in_year,
    get_all_weeks_in_year,
    get_cycle_bounds,
    get_week_bounds,
)

def get_leaves_dashboard_data(
    user, period, cycle_num, week_num, year, query_employee_id
):
    """
    Assembles context needed for the Leaves Dashboard.
    """
    is_superuser = user.is_superuser
    role, section = resolve_user_role_and_section(user)
    scope = RBACService.get_scope(user)

    if period not in ("daily", "weekly", "monthly"):
        period = "daily"

    today = datetime.now().date()
    current_year = today.year

    try:
        year_val = int(year or current_year)
    except (ValueError, TypeError):
        year_val = current_year

    all_cycles = get_all_cycles_in_year(year_val)
    all_weeks = get_all_weeks_in_year(year_val)

    if period == "daily":
        yesterday = today - timedelta(days=1)
        start_date = yesterday
        end_date = yesterday
    elif period == "weekly":
        if week_num:
            try:
                start_date, end_date = get_week_bounds(int(week_num), year_val)
            except (ValueError, TypeError):
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
        else:
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
    else:  # monthly
        if cycle_num:
            try:
                cycles = get_all_cycles_in_year(year_val)
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

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # Get employee ID
    has_selected_employee = False
    if scope == "OWN" and not is_superuser:
        employee_id = user.username
    else:
        employee_id = query_employee_id
        if employee_id and employee_id.strip():
            has_selected_employee = True
            employee_id = employee_id.strip()
        else:
            employee_id = ""

    attendance = []
    try:
        fetch_emp_id = employee_id if employee_id else ""
        attendance = fetch_attendance(
            employee_id=fetch_emp_id, start_date=start_str, end_date=end_str
        )
    except Exception as e:
        print(f"Error fetching attendance in leaves dashboard: {e}")

    # Filter data based on RBAC rules and resolved section names
    expected_dtname4 = get_expected_dtname4(role, section, user.username)
    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

    if scope == "OWN" or (not is_supervisor and not is_superuser):
        # Regular employee sees only their own data
        attendance = [r for r in attendance if r.get("Employee ID") == user.username]
    elif is_superuser or scope == "ALL":
        # Superuser / ALL scope sees everyone
        if employee_id:
            attendance = [r for r in attendance if r.get("Employee ID") == employee_id]
    else:
        # Supervisor/Manager scope: filter by section name (dtName4 / Day)
        if expected_dtname4:
            if employee_id:
                # Specific employee: verify they belong to our section
                attendance = [
                    r for r in attendance 
                    if r.get("Employee ID") == employee_id and r.get("Day") == expected_dtname4
                ]
            else:
                # Group view: show all records in our section
                attendance = [r for r in attendance if r.get("Day") == expected_dtname4]
        else:
            # Fallback to accessible users if no expected section name is resolved
            accessible_users = set(
                RBACService.get_accessible_employees(user).values_list("user__username", flat=True)
            )
            if employee_id:
                if employee_id in accessible_users:
                    attendance = [r for r in attendance if r.get("Employee ID") == employee_id]
                else:
                    attendance = []
            else:
                attendance = [r for r in attendance if r.get("Employee ID") in accessible_users]

    stats = {"mispunch": 0, "leave": 0, "short_leave": 0, "half_day": 0, "full_day": 0}
    records = []

    for record in attendance:
        go1 = record.get("In Time", "").strip()
        out1 = record.get("Out Time", "").strip()

        # Determine if it's a Sunday (weekday == 6)
        date_obj = parse_date(record.get("Date", ""))
        is_sunday = date_obj.weekday() == 6 if date_obj else False
        is_today = (date_obj.date() == datetime.now().date()) if date_obj else False

        # Treat "00:00" and "—" as blank
        if go1 in ("00:00", "—"):
            go1 = ""
        if out1 in ("00:00", "—"):
            out1 = ""

        category = ""
        try:
            work_hrs = float(record.get("Working Hours", 0) or 0)
        except (ValueError, TypeError):
            work_hrs = 0.0

        is_holiday = (
            date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1
            if date_obj
            else False
        )

        if not go1 and not out1:
            if not is_sunday and not is_holiday and not record.get("Leave Type"):
                category = "Absent"
                stats["leave"] += 1
        elif not go1 or not out1:
            if not is_sunday and not is_holiday and not record.get("Leave Type"):
                if is_today:
                    category = "Present"
                else:
                    category = "Mispunch"
                    stats["mispunch"] += 1
        else:
            # Check shift timings to validate short leave
            shift_str = str(record.get("Shift") or "")

            # Default to 09:00 - 18:00 if no match
            shift_in, shift_out = 9 * 60, 18 * 60
            match = re.search(r"(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})", shift_str)
            if match:
                sh, sm, eh, em = map(int, match.groups())
                shift_in = sh * 60 + sm
                shift_out = eh * 60 + em

            def to_mins(t_str):
                try:
                    h, m = map(int, t_str.split(":"))
                    return h * 60 + m
                except (ValueError, TypeError, AttributeError):
                    return 0

            actual_in = to_mins(go1)
            actual_out = to_mins(out1)

            late_mins = actual_in - shift_in if actual_in >= shift_in else 0
            early_mins = shift_out - actual_out if shift_out >= actual_out else 0

            # Validate short leave: missing ~2 hours at start OR ~2 hours at end (90 to 180 mins)
            is_valid_short_leave = (90 <= late_mins <= 180) or (90 <= early_mins <= 180)

            if work_hrs >= 8.0:
                category = "Full Day"
                stats["full_day"] += 1
            elif work_hrs >= 5.5 and is_valid_short_leave:
                # Validated 2-hour absence at the start or end of the shift
                category = "Short Leave"
                stats["short_leave"] += 1
            else:
                # Default to Half Day if it doesn't meet Full Day or Valid Short Leave criteria
                category = "Half Day"
                stats["half_day"] += 1

        if category:
            records.append(
                {
                    "date": (
                        date_obj.strftime("%d/%m/%Y")
                        if date_obj
                        else record.get("Date", "")
                    ),
                    "day": date_obj.strftime("%A") if date_obj else "",
                    "in_time": go1 or "—",
                    "out_time": out1 or "—",
                    "working_hours": f"{work_hrs}h",
                    "category": category,
                    "employee_id": record.get("Employee ID", "—"),
                    "employee_name": record.get("Employee Name", "—"),
                    "department": record.get("Day", "—"),
                }
            )

    # Sort records by date descending
    records.sort(key=lambda x: parse_date(x["date"]) or datetime.min, reverse=True)

    # Default selected_week and selected_cycle to current week/cycle if not specified
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

    return {
        "active_tab": "leaves",
        "records": records,
        "stats": stats,
        "start_date": start_str,
        "end_date": end_str,
        "role_display": (
            user.profile.role.name
            if (hasattr(user, "profile") and user.profile.role)
            else ("Admin" if is_superuser else "User")
        ),
        "all_cycles": all_cycles,
        "all_weeks": all_weeks,
        "selected_cycle": selected_cycle,
        "selected_week": selected_week,
        "current_year": current_year,
        "role": role,
        "is_superuser": is_superuser,
        "has_selected_employee": has_selected_employee,
        "period": period,
    }
