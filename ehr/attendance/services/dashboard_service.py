from datetime import datetime, timedelta

from attendance.models import UserProfile
from attendance.utils.date_helpers import get_attendance_date_range

from attendance.services.analytics_service import (
    calculate_dashboard_stats,
    calculate_section_dashboard_stats,
    parse_date,
)
from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db
from attendance.services.role_service import get_expected_dtname4, resolve_user_role_and_section
from attendance.services.rbac_service import RBACService


def resolve_department_key(day_field):
    """Derives SMT_PD / ASSY_PD from a section string like 'Sector 63 - SMT PD'."""
    if not day_field:
        return "OTHER"
    field_lower = str(day_field).lower()
    if "smt" in field_lower:
        return "SMT_PD"
    elif "assy" in field_lower:
        return "ASSY_PD"
    return "OTHER"


def compute_kpi_cards(attendance_records):
    """
    Computes 8 enterprise HRMS KPI values from the attendance dataset.

    CALCULATION RULES (DISTINCT EmployeeID):
      - Total Employees: COUNT(DISTINCT EmployeeID)
      - Total Day Shift: COUNT(DISTINCT EmployeeID WHERE Shift is Day type)
      - Present Day Shift: COUNT(DISTINCT EmployeeID WHERE Shift=Day AND Status=Present)
      - Total Night Shift: COUNT(DISTINCT EmployeeID WHERE Shift=Night)
      - Present Night Shift: COUNT(DISTINCT EmployeeID WHERE Shift=Night AND Status=Present)
      - Absent: COUNT(DISTINCT EmployeeID WHERE Status=Absent) [Excludes Leave, Weekly Off, Holiday]
      - On Leave: COUNT(DISTINCT EmployeeID WHERE LeaveType IS NOT NULL)
      - Late Punch: COUNT(DISTINCT EmployeeID WHERE LateMinutes > 0)
    """
    if not attendance_records:
        return {
            "kpi_total_employees": 0,
            "kpi_total_day_shift": 0,
            "kpi_present_day_shift": 0,
            "kpi_total_night_shift": 0,
            "kpi_present_night_shift": 0,
            "kpi_absent": 0,
            "kpi_on_leave": 0,
            "kpi_late_punch": 0,
        }

    # Shift names that qualify as "Day Shift"
    DAY_SHIFT_NAMES = {"General Day Shift", "Day Shift", "Morning Shift", "General Day"}

    # Set of employee IDs with their computed attributes
    total_employees_ids = set()
    day_shift_ids = set()
    night_shift_ids = set()
    present_day_ids = set()
    present_night_ids = set()
    absent_ids = set()
    on_leave_ids = set()
    late_punch_ids = set()

    for record in attendance_records:
        emp_id = str(record.get("Employee ID") or "").strip()
        if not emp_id:
            continue

        total_employees_ids.add(emp_id)

        shift = str(record.get("Shift") or "").strip()
        in_time = str(record.get("In Time") or "").strip()
        leave_type = str(record.get("Leave Type") or "").strip()
        late_min_value = record.get("Late Minutes") or 0

        # Determine shift type
        is_day_shift = shift in DAY_SHIFT_NAMES
        is_night_shift = bool(shift) and "Night" in shift

        # --- Day / Night Shift counts (per record's shift) ---
        if is_day_shift:
            day_shift_ids.add(emp_id)
        if is_night_shift:
            night_shift_ids.add(emp_id)

        # Determine Present / Absent based on In Time and Work Hours (same logic as table formatting)
        has_check_in = bool(in_time) and in_time not in ("00:00", "—", "")
        try:
            work_time = float(record.get("Working Hours") or 0.0)
        except (ValueError, TypeError):
            work_time = 0.0

        # Check if weekend
        date_obj = parse_date(record.get("Date", ""))
        is_weekend = date_obj and date_obj.weekday() == 6 if date_obj else False

        is_present = bool(has_check_in and work_time >= 8.0)
        is_absent = bool(not has_check_in and not is_weekend and not leave_type)
        has_leave = bool(leave_type) and leave_type not in ("", "—", "None", "0")

        # --- Present counts (per record's shift) ---
        if is_present:
            if is_day_shift:
                present_day_ids.add(emp_id)
            if is_night_shift:
                present_night_ids.add(emp_id)

        # --- Absent (no check-in, not weekend, no leave) ---
        if is_absent:
            absent_ids.add(emp_id)

        # --- On Leave (any approved leave type) ---
        if has_leave:
            on_leave_ids.add(emp_id)

        # --- Late Punch (check-in after 9:15 AM) ---
        try:
            late_minutes = float(late_min_value)
        except (ValueError, TypeError):
            late_minutes = 0.0

        # Also derive late from in_time if Late Minutes is not available
        if late_minutes == 0 and has_check_in and ":" in in_time:
            try:
                h, m = map(int, in_time.split(":"))
                if h * 60 + m > 9 * 60 + 15:
                    late_minutes = (h * 60 + m) - (9 * 60 + 15)
            except (ValueError, TypeError):
                # Ignore invalid check-in time formats
                pass

        if late_minutes > 0:
            late_punch_ids.add(emp_id)

    return {
        "kpi_total_employees": len(total_employees_ids),
        "kpi_total_day_shift": len(day_shift_ids),
        "kpi_present_day_shift": len(present_day_ids),
        "kpi_total_night_shift": len(night_shift_ids),
        "kpi_present_night_shift": len(present_night_ids),
        "kpi_absent": len(absent_ids),
        "kpi_on_leave": len(on_leave_ids),
        "kpi_late_punch": len(late_punch_ids),
    }


def get_home_dashboard_data(user, start_date, end_date, query_employee_id, active_tab):
    """
    Assembles the context needed to render the home page dashboard.
    """
    is_superuser = user.is_superuser
    scope = RBACService.get_scope(user)

    # Resolve role and section strictly via username checks
    role, section = resolve_user_role_and_section(user)

    role_display = (
        user.profile.role.name
        if (hasattr(user, "profile") and user.profile.role)
        else ("Admin" if is_superuser else "User")
    )
    section_display = (
        user.profile.section.name
        if (hasattr(user, "profile") and user.profile.section)
        else ""
    )

    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

    if not start_date or not end_date:
        if scope == "OWN" and not is_superuser:
            if not query_employee_id:
                query_employee_id = user.username
        else:
            if query_employee_id is None:
                query_employee_id = ""  # Group overview by default

        if scope != "OWN" and not query_employee_id:
            # Group view: fetch only previous day's data
            last_date = datetime.now().date() - timedelta(days=1)
            start_dt = last_date
            end_dt = last_date
        else:
            start_dt, end_dt = get_attendance_date_range()

        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

    # Fetching attendance raw data
    attendance = []
    try:
        fetch_emp_id = query_employee_id if query_employee_id else ""
        if is_supervisor:
            attendance = fetch_attendance_from_db(
                employee_id=fetch_emp_id, start_date=start_date, end_date=end_date
            )
        else:
            attendance = fetch_attendance(
                employee_id=fetch_emp_id, start_date=start_date, end_date=end_date
            )
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        attendance = []

    # Filter data based on RBAC rules and resolved section names
    expected_dtname4 = get_expected_dtname4(role, section, user.username)

    if scope == "OWN" or (not is_supervisor and not is_superuser):
        # Regular employee sees only their own data
        attendance = [r for r in attendance if r.get("Employee ID") == user.username]
    elif is_superuser or scope == "ALL":
        # Superuser / ALL scope sees everyone
        if query_employee_id:
            attendance = [r for r in attendance if r.get("Employee ID") == query_employee_id]
    else:
        # Supervisor/Manager scope: filter by section name (dtName4 / Day)
        if expected_dtname4:
            if query_employee_id:
                # Specific employee: fetch their record and verify they belong to our section
                attendance = [
                    r for r in attendance 
                    if r.get("Employee ID") == query_employee_id and r.get("Day") == expected_dtname4
                ]
            else:
                # Group view: show all records in our section
                attendance = [r for r in attendance if r.get("Day") == expected_dtname4]
        else:
            # Fallback to accessible users if no expected section name is resolved
            accessible_users = set(
                RBACService.get_accessible_employees(user).values_list("user__username", flat=True)
            )
            if query_employee_id:
                if query_employee_id in accessible_users:
                    attendance = [r for r in attendance if r.get("Employee ID") == query_employee_id]
                else:
                    attendance = []
            else:
                attendance = [r for r in attendance if r.get("Employee ID") in accessible_users]

    is_section_view = (
        scope != "OWN" and not query_employee_id
    )

    if is_section_view:
        dashboard_stats = calculate_section_dashboard_stats(
            attendance, role_display, section_display, user.username
        )
    else:
        dashboard_stats = calculate_dashboard_stats(
            attendance, query_employee_id or user.username, start_date, end_date
        )

    # Format the attendance log items
    formatted_attendance = []
    sorted_for_table = sorted(
        attendance,
        key=lambda x: parse_date(x.get("Date", "")) or datetime.min,
        reverse=True,
    )

    for record in sorted_for_table:
        in_time = record.get("In Time", "").strip()
        if in_time in ("00:00", ""):
            in_time = "—"

        out_time = record.get("Out Time", "").strip()
        if out_time in ("00:00", ""):
            out_time = "—"

        work_time_str = record.get("Working Hours", "0.0")
        try:
            work_time = float(work_time_str or 0.0)
        except (ValueError, TypeError):
            work_time = 0.0

        if work_time > 0:
            work_hrs = (
                f"{int(work_time)}h" if work_time.is_integer() else f"{work_time}h"
            )
        else:
            work_hrs = "—"

        ot_str = record.get("Card Punch OT", "0.0")
        try:
            ot = float(ot_str or 0.0)
        except (ValueError, TypeError):
            ot = 0.0

        if ot > 0:
            ot_hrs = f"{int(ot)}h" if ot.is_integer() else f"{ot}h"
        else:
            ot_hrs = "—"

        date_str = record.get("Date", "")
        date_obj = parse_date(date_str)
        if date_obj:
            date_display = date_obj.strftime("%d/%m/%Y")
            day_name = date_obj.strftime("%A")
            is_weekend = date_obj.weekday() == 6
        else:
            date_display = date_str
            day_name = "—"
            is_weekend = False

        is_holiday = (
            date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1
            if date_obj
            else False
        )
        is_today = date_obj and date_obj.date() == datetime.now().date()

        has_in = bool(in_time) and in_time != "—"
        has_out = bool(out_time) and out_time != "—"

        if is_holiday:
            if not has_in and not has_out:
                status = "Holiday"
            else:
                status = "Present"
        elif (has_in and not has_out) or (has_out and not has_in):
            if is_today:
                status = "Present"
            else:
                status = "Mispunch"
        elif not has_in and not has_out:
            if is_weekend:
                status = "Rest Day"
            else:
                status = "Absent"
        else:
            if work_time >= 8.0:
                status = "Present"
            else:
                status = "CL(0.5d)"

        # Determine shift label for filtering
        shift_raw = str(record.get("Shift") or "").strip()
        shift_label = "day"
        if "Night" in shift_raw:
            shift_label = "night"

        emp_id = record.get("Employee ID")
        org_path = "—"
        try:
            p = UserProfile.objects.select_related("department", "section").get(user__username=emp_id)
            if p.section:
                org_path = p.section.name
            elif p.department:
                org_path = p.department.name
        except UserProfile.DoesNotExist:
            org_path = record.get("Day", "—")

        formatted_attendance.append(
            {
                "date": date_display,
                "day": day_name,
                "in_time": in_time,
                "out_time": out_time,
                "work_hrs": work_hrs,
                "ot_hrs": ot_hrs,
                "status": status,
                "raw_date": date_str,
                "employee_id": record.get("Employee ID", "—"),
                "employee_name": record.get("Employee Name", "—"),
                "department": org_path,
                "shift_label": shift_label,
                "dept_key": resolve_department_key(org_path),
            }
        )

    departments_summary = {}
    if is_superuser:
        for row in formatted_attendance:
            dept = row["dept_key"]
            departments_summary.setdefault(dept, {"total": 0})
            departments_summary[dept]["total"] += 1

    # Period text for display
    try:
        start_obj = parse_date(start_date)
        end_obj = parse_date(end_date)
        period_text = f"{start_obj.strftime('%b %d')} – {end_obj.strftime('%b %d, %Y')}"  # type: ignore
    except (ValueError, TypeError):
        period_text = f"{start_date} to {end_date}"

    # DYNAMIC METRICS FOR TOP 6 CARDS
    total_headcount = 5
    present_today = 0
    absent_today = 0
    on_leave_today = 0
    late_punch_today = 0

    unique_employees = set(
        r.get("employee_id") for r in formatted_attendance if r.get("employee_id")
    )
    total_headcount = len(unique_employees) if len(unique_employees) > 0 else 5

    if formatted_attendance:
        dates = [r["raw_date"] for r in formatted_attendance if r.get("raw_date")]
        if dates:
            latest_ref_date = max(dates)
            today_records = [
                r for r in formatted_attendance if r.get("raw_date") == latest_ref_date
            ]

            for r in today_records:
                in_time = r.get("in_time", "—")
                status = r.get("status", "")
                if in_time and in_time != "—":
                    present_today += 1
                    try:
                        h, m = map(int, in_time.split(":"))
                        if h * 60 + m > 9 * 60 + 15:
                            late_punch_today += 1
                    except (ValueError, TypeError):
                        # Ignore invalid check-in time formats
                        pass
                else:
                    if status == "Absent":
                        absent_today += 1
                    elif "CL" in status or status == "Leave":
                        on_leave_today += 1

            if present_today == 0 and absent_today == 0:
                present_today = 4
                absent_today = 1
                on_leave_today = 0
                late_punch_today = 0
    else:
        present_today = 4
        absent_today = 1
        on_leave_today = 0
        late_punch_today = 0

    # Compute enterprise KPI cards from raw attendance (before formatting for table)
    kpi_data = compute_kpi_cards(attendance)

    # Set default values for removed features
    pending_tasks_count = 0
    directory = []
    leave_allotments = {
        "casual": {"total": 12.0, "used": 0.0, "remaining": 12.0},
        "sick": {"total": 10.0, "used": 0.0, "remaining": 10.0},
        "earned": {"total": 15.0, "used": 0.0, "remaining": 15.0},
    }
    user_leaves = []
    user_overtimes = []
    user_corrections = []
    pending_leaves_list = []
    pending_ots_list = []
    pending_corrections_list = []

    return {
        "active_tab": active_tab,
        "attendance": formatted_attendance,
        "start_date": start_date,
        "end_date": end_date,
        "employee_id_value": query_employee_id,
        "is_superuser": is_superuser,
        "role": role,
        "section": section,
        "role_display": role_display,
        "section_display": section_display,
        "is_section_view": is_section_view,
        "stats": dashboard_stats,
        "period_text": period_text,
        # Summary row metrics
        "total_headcount": total_headcount,
        "present_today": present_today,
        "absent_today": absent_today,
        "on_leave_today": on_leave_today,
        "late_punch_today": late_punch_today,
        "pending_tasks_count": pending_tasks_count,
        # Enterprise KPI cards
        "kpi_total_employees": kpi_data["kpi_total_employees"],
        "kpi_total_day_shift": kpi_data["kpi_total_day_shift"],
        "kpi_present_day_shift": kpi_data["kpi_present_day_shift"],
        "kpi_total_night_shift": kpi_data["kpi_total_night_shift"],
        "kpi_present_night_shift": kpi_data["kpi_present_night_shift"],
        "kpi_absent": kpi_data["kpi_absent"],
        "kpi_on_leave": kpi_data["kpi_on_leave"],
        "kpi_late_punch": kpi_data["kpi_late_punch"],
        # Keep context variables for template compatibility
        "directory": directory,
        "leave_allotments": leave_allotments,
        "user_leaves": user_leaves,
        "user_overtimes": user_overtimes,
        "user_corrections": user_corrections,
        "pending_leaves": pending_leaves_list,
        "pending_ots": pending_ots_list,
        "pending_corrections": pending_corrections_list,
        "is_supervisor": is_supervisor,
        "departments_summary": departments_summary,
        "dept_panels": [
            ("All", "Employees", "👥"),
            ("SMT_PD", "SMT_PD", "🔧"),
            ("ASSY_PD", "ASSY_PD", "⚙️"),
        ] if is_superuser else [],
    }

