import logging
from datetime import datetime, timedelta

from attendance.models import UserProfile
from attendance.utils.date_helpers import get_attendance_date_range, get_shift_start_minutes

from attendance.services.analytics_service import (
    calculate_dashboard_stats,
    calculate_section_dashboard_stats,
    parse_date,
)
from attendance.services.attendance_service import get_attendance
from attendance.services.role_service import get_expected_dtname4, resolve_user_role_and_section
from attendance.services.rbac_service import RBACService

logger = logging.getLogger(__name__)


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


def _compute_status_for_record(record, date_obj):
    """
    Compute the attendance status for a single raw attendance record dict.
    Returns (status, is_present, is_absent, has_leave, late_minutes, is_late, is_night_shift, shift_label)
    """
    in_time = str(record.get("In Time") or "").strip()
    out_time = str(record.get("Out Time") or "").strip()
    leave_type = str(record.get("Leave Type") or "").strip()
    has_check_in = bool(in_time) and in_time not in ("00:00", "—", "")
    has_check_out = bool(out_time) and out_time not in ("00:00", "—", "")
    
    try:
        work_time = float(record.get("Working Hours") or 0.0)
    except (ValueError, TypeError):
        work_time = 0.0

    is_weekend = date_obj and date_obj.weekday() == 6 if date_obj else False
    is_holiday = date_obj and date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1
    
    # Determine shift
    shift_raw = str(record.get("Shift") or "").strip()
    is_night_shift = bool(shift_raw) and "Night" in shift_raw
    shift_label = "night" if is_night_shift else "day"

    # Late minutes calculation
    late_minutes = 0.0
    if has_check_in and ":" in in_time:
        try:
            h, m = map(int, in_time.split(":"))
            wt_id = record.get("WT ID") or record.get("WTID")
            shift_start = get_shift_start_minutes(wt_id, is_night_shift, in_time)
            if h * 60 + m > shift_start:
                late_minutes = float((h * 60 + m) - shift_start)
        except (ValueError, TypeError):
            pass
    
    if late_minutes == 0:
        try:
            late_minutes = float(record.get("Late Minutes") or 0.0)
        except (ValueError, TypeError):
            late_minutes = 0.0

    is_late = late_minutes > 0.0
    has_leave = bool(leave_type) and leave_type not in ("", "—", "None", "0")

    # Determine status
    is_mispunch = False

    is_today = False
    if date_obj:
        if hasattr(date_obj, "date"):
            is_today = (date_obj.date() == datetime.now().date())
        else:
            is_today = (date_obj == datetime.now().date())

    if is_holiday:
        if has_check_in or has_check_out:
            status = "Present"
        else:
            status = "Holiday"
    elif is_today and has_check_in and not is_late and not has_check_out:
        status = "Present"
    elif (has_check_in and not has_check_out) or (has_check_out and not has_check_in):
        # Only check if it's a mispunch — for past dates, partial punch is always mispunch
        status = "Mispunch"
        is_mispunch = True
    elif not has_check_in and not has_check_out:
        if is_weekend:
            status = "Rest Day"
        elif has_leave:
            status = "Leave"
        else:
            status = "Absent"
    else:
        if work_time >= 8.0:
            status = "Present"
        else:
            status = "CL(0.5d)"

    is_present = status == "Present"
    is_absent = status == "Absent"

    return status, is_present, is_absent, has_leave, late_minutes, is_late, is_night_shift, shift_label


def get_filtered_attendance_record_queryset(user, role, section, query_employee_id, start_date, end_date):
    from attendance.models import AttendanceRecord
    from attendance.services.rbac_service import RBACService
    from attendance.services.role_service import get_expected_dtname4
    from datetime import datetime

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif isinstance(end_date, datetime):
        end_date = end_date.date()

    is_superuser = user.is_superuser
    scope = RBACService.get_scope(user)
    is_section_view = (scope != "OWN" and not query_employee_id)

    # Base query by date range
    qs = AttendanceRecord.objects.filter(attendance_date__range=(start_date, end_date))

    # Apply employee ID filter if specific employee is queried
    if query_employee_id:
        qs = qs.filter(employee_id=query_employee_id)

    # Apply RBAC / section filtering
    if not is_section_view:
        # Regular employee: only own data
        qs = qs.filter(employee_id=user.username)
    elif is_superuser or scope == "ALL":
        # Superuser / ALL scope sees everyone
        pass
    else:
        # Supervisor/Manager scope: filter by section name (day / dtName4)
        expected_dtname4 = get_expected_dtname4(role, section, user.username)
        if expected_dtname4:
            qs = qs.filter(day=expected_dtname4)
        else:
            # Fallback to accessible users
            accessible_users = list(
                RBACService.get_accessible_employees(user).values_list("user__username", flat=True)
            )
            qs = qs.filter(employee_id__in=accessible_users)

    return qs


def calculate_dashboard_summary_from_db(qs):
    from django.db.models import Q, Case, When, Value, CharField, BooleanField, IntegerField, F, Sum, Avg, Count
    from datetime import date

    # Define condition components matching _compute_status_for_record
    q_holiday = Q(attendance_date=date(2026, 7, 1))
    q_has_in = ~Q(in_time__in=["", "00:00", "—", "None"]) & Q(in_time__isnull=False)
    q_has_out = ~Q(out_time__in=["", "00:00", "—", "None"]) & Q(out_time__isnull=False)
    has_leave = ~Q(leave_type__in=["", "—", "None", "0"]) & Q(leave_type__isnull=False)

    q_today = Q(attendance_date=date.today())
    cond_today_on_time_present = q_today & q_has_in & ~q_has_out & (Q(late_minutes=0.0) | Q(late_minutes__isnull=True))

    cond_holiday_present = q_holiday & (q_has_in | q_has_out)
    cond_holiday_absent = q_holiday & ~(q_has_in | q_has_out)
    cond_mispunch = ~q_holiday & ~cond_today_on_time_present & ((q_has_in & ~q_has_out) | (~q_has_in & q_has_out))
    q_no_punch = ~q_has_in & ~q_has_out
    cond_rest_day = ~q_holiday & q_no_punch & Q(attendance_date__week_day=1)
    cond_leave = ~q_holiday & q_no_punch & ~Q(attendance_date__week_day=1) & has_leave
    cond_absent = ~q_holiday & q_no_punch & ~Q(attendance_date__week_day=1) & ~has_leave
    cond_present = ~q_holiday & (
        (q_has_in & q_has_out & Q(working_hours__gte=8.0)) |
        cond_today_on_time_present
    )
    cond_cl = ~q_holiday & ~cond_today_on_time_present & q_has_in & q_has_out & Q(working_hours__lt=8.0)

    # Shift checks
    q_night_shift = Q(shift__contains="Night")
    q_day_shift = ~Q(shift__contains="Night") & ~Q(shift="") & Q(shift__isnull=False)

    # Boolean filters
    is_present_q = Q(cond_holiday_present | cond_present | cond_cl)
    is_absent_q = Q(cond_absent)
    has_leave_q = Q(cond_leave)

    metrics = qs.aggregate(
        working_days=Count("attendance_date", distinct=True),
        total_employees=Count("employee_id", distinct=True),
        
        kpi_total_employees=Count("id"),
        kpi_total_day_shift=Count("id", filter=q_day_shift),
        kpi_total_night_shift=Count("id", filter=q_night_shift),
        
        kpi_present_day_shift=Count("id", filter=is_present_q & q_day_shift),
        kpi_present_night_shift=Count("id", filter=is_present_q & q_night_shift),
        
        kpi_absent=Count("id", filter=is_absent_q),
        kpi_on_leave=Count("id", filter=has_leave_q),
        kpi_late_punch=Count("id", filter=Q(late_minutes__gt=0.0)),
        
        # Grid metrics
        days_present=Sum(Case(When(is_present_q, then=1.0), default=0.0)),
        leaves_taken=Sum(Case(When(is_absent_q | has_leave_q, then=1.0), default=0.0)),
        late_arrivals=Count("id", filter=Q(late_minutes__gt=0.0)),
        mispunches=Count("id", filter=Q(cond_mispunch)),
        total_ot=Sum("card_punch_ot"),
        
        # Average work time
        total_work_time=Sum(Case(When(q_has_in & q_has_out & Q(working_hours__gt=0.0), then=F("working_hours")), default=0.0)),
        work_time_count=Count("id", filter=q_has_in & q_has_out & Q(working_hours__gt=0.0)),
        
        # Breakdowns for chart
        breakdown_present=Count("id", filter=cond_present | cond_holiday_present),
        breakdown_leave=Count("id", filter=cond_leave | cond_absent),
        breakdown_rest=Count("id", filter=cond_rest_day | cond_holiday_absent),
        breakdown_mispunch=Count("id", filter=cond_mispunch),
        breakdown_cl=Count("id", filter=cond_cl),
    )

    # Compute derived fields
    work_time_count = metrics["work_time_count"] or 0
    total_work_time = metrics["total_work_time"] or 0.0
    avg_work_time = round(total_work_time / work_time_count, 1) if work_time_count > 0 else 0.0
    total_ot = round(metrics["total_ot"] or 0.0, 1)

    days_present_val = int(metrics["days_present"] or 0.0)
    leaves_taken_val = int(metrics["leaves_taken"] or 0.0)

    late_arrivals_count = metrics["late_arrivals"] or 0
    mispunch_count = metrics["mispunches"] or 0

    if (metrics["total_employees"] or 0) > 1:
        late_details = f"{late_arrivals_count} late check-ins"
        mispunch_details = f"{mispunch_count} records" if mispunch_count > 0 else "No mispunches"
    else:
        # Find max late minutes directly in SQLite
        max_late_val = qs.filter(late_minutes__gt=0.0).order_by("-late_minutes").values("late_minutes", "attendance_date").first()
        if max_late_val:
            dt_display = max_late_val["attendance_date"].strftime("%d/%m") if max_late_val["attendance_date"] else ""
            late_details = f"{int(max_late_val['late_minutes'])} min late ({dt_display})"
        else:
            late_details = "No late arrivals"
        mispunch_details = f"{mispunch_count} records" if mispunch_count > 0 else "No mispunches"

    return {
        "working_days": metrics["working_days"] or 0,
        "present_count": metrics["kpi_present_day_shift"] + metrics["kpi_present_night_shift"],
        "absent_count": metrics["kpi_absent"] or 0,
        "leave_count": metrics["kpi_on_leave"] or 0,
        "late_arrivals": late_arrivals_count,
        "mispunches": mispunch_count,
        "avg_work_time": avg_work_time,
        "total_employees": metrics["kpi_total_employees"] or 0,
        "day_shift_count": metrics["kpi_total_day_shift"] or 0,
        "night_shift_count": metrics["kpi_total_night_shift"] or 0,
        "present_day_shift": metrics["kpi_present_day_shift"] or 0,
        "present_night_shift": metrics["kpi_present_night_shift"] or 0,
        "days_present": days_present_val,
        "leaves_taken": leaves_taken_val,
        "late_details": late_details,
        "mispunch_details": mispunch_details,
        "total_ot": total_ot,
        "breakdown_data": [
            metrics["breakdown_present"] or 0,
            metrics["breakdown_leave"] or 0,
            metrics["breakdown_rest"] or 0,
            metrics["breakdown_mispunch"] or 0,
            metrics["breakdown_cl"] or 0,
        ],
        "kpi_total_employees": metrics["kpi_total_employees"] or 0,
        "kpi_total_day_shift": metrics["kpi_total_day_shift"] or 0,
        "kpi_present_day_shift": metrics["kpi_present_day_shift"] or 0,
        "kpi_total_night_shift": metrics["kpi_total_night_shift"] or 0,
        "kpi_present_night_shift": metrics["kpi_present_night_shift"] or 0,
        "kpi_absent": metrics["kpi_absent"] or 0,
        "kpi_on_leave": metrics["kpi_on_leave"] or 0,
        "kpi_late_punch": metrics["kpi_late_punch"] or 0,
    }


def calculate_dashboard_summary(attendance_records):
    from django.db.models import QuerySet
    if isinstance(attendance_records, QuerySet):
        return calculate_dashboard_summary_from_db(attendance_records)

    """
    Calculate ALL dashboard KPIs from a single set of filtered attendance records.
    Calculate ALL dashboard KPIs from a single set of filtered attendance records.
    
    This is the ONE source of truth for all KPI calculations on the dashboard.
    Every KPI card and the attendance table use the exact same dataset.
    """
    if not attendance_records:
        return {
            "working_days": 0,
            "present_count": 0,
            "absent_count": 0,
            "leave_count": 0,
            "late_arrivals": 0,
            "mispunches": 0,
            "avg_work_time": 0.0,
            "total_employees": 0,
            "day_shift_count": 0,
            "night_shift_count": 0,
            "present_day_shift": 0,
            "present_night_shift": 0,
            "days_present": 0.0,
            "leaves_taken": 0.0,
            "late_details": "No late arrivals",
            "mispunch_details": "No mispunches",
            "total_ot": 0.0,
            "breakdown_data": [0, 0, 0, 0, 0],
            "kpi_total_employees": 0,
            "kpi_total_day_shift": 0,
            "kpi_present_day_shift": 0,
            "kpi_total_night_shift": 0,
            "kpi_present_night_shift": 0,
            "kpi_absent": 0,
            "kpi_on_leave": 0,
            "kpi_late_punch": 0,
        }

    unique_dates = set()
    all_employee_ids = set()
    day_shift_ids = set()
    night_shift_ids = set()
    
    total_employees_count = 0
    day_shift_count = 0
    night_shift_count = 0
    present_day_count = 0
    present_night_count = 0
    present_all_count = 0
    absent_count = 0
    leave_count = 0
    late_count = 0

    days_present = 0.0
    leaves_taken = 0.0
    late_arrivals_count = 0
    mispunch_count = 0
    total_ot = 0.0

    total_work_time = 0.0
    work_time_count = 0

    max_late_minutes = 0
    max_late_date = ""

    breakdown_present = 0
    breakdown_leave = 0
    breakdown_rest = 0
    breakdown_mispunch = 0
    breakdown_cl = 0

    for record in attendance_records:
        dt_str = record.get("Date") or record.get("attendance_date")
        date_obj = parse_date(dt_str)
        if date_obj:
            unique_dates.add(date_obj.date())

        emp_id = str(record.get("Employee ID") or "").strip()
        if not emp_id:
            continue
        all_employee_ids.add(emp_id)

        shift_raw = str(record.get("Shift") or "").strip()
        is_night_shift = bool(shift_raw) and "Night" in shift_raw
        is_day_shift = bool(shift_raw) and not is_night_shift

        if is_day_shift:
            day_shift_ids.add(emp_id)
        if is_night_shift:
            night_shift_ids.add(emp_id)

        total_employees_count += 1
        if is_day_shift:
            day_shift_count += 1
        if is_night_shift:
            night_shift_count += 1

        status, is_present, is_absent, has_leave, late_minutes, is_late, _, _ = _compute_status_for_record(record, date_obj)

        is_present = status in ("Present", "CL(0.5d)")
        is_absent = status == "Absent"
        has_leave = status == "Leave"

        try:
            ot = float(record.get("Card Punch OT") or 0.0)
        except (ValueError, TypeError):
            ot = 0.0
        total_ot += ot

        if is_present:
            present_all_count += 1
            if is_day_shift:
                present_day_count += 1
            if is_night_shift:
                present_night_count += 1

        if is_absent:
            absent_count += 1

        if has_leave:
            leave_count += 1

        if is_late:
            late_count += 1

        if status == "Present":
            days_present += 1.0
            breakdown_present += 1
        elif status == "CL(0.5d)":
            days_present += 1.0
            breakdown_cl += 1
        elif status == "Leave":
            leaves_taken += 1.0
            breakdown_leave += 1
        elif status == "Absent":
            leaves_taken += 1.0
            breakdown_leave += 1
        elif status == "Mispunch":
            mispunch_count += 1
            breakdown_mispunch += 1
        elif status in ("Rest Day", "Holiday"):
            breakdown_rest += 1

        if is_late:
            late_arrivals_count += 1
            if late_minutes > max_late_minutes:
                max_late_minutes = int(late_minutes)
                if date_obj:
                    max_late_date = date_obj.strftime("%d/%m")

        in_time = str(record.get("In Time") or "").strip()
        out_time = str(record.get("Out Time") or "").strip()
        has_check_in = bool(in_time) and in_time not in ("00:00", "—", "")
        has_check_out = bool(out_time) and out_time not in ("00:00", "—", "")
        if has_check_in and has_check_out:
            try:
                work_time = float(record.get("Working Hours") or 0.0)
            except (ValueError, TypeError):
                work_time = 0.0
            if work_time > 0.0:
                total_work_time += work_time
                work_time_count += 1

    working_days = len(unique_dates)
    avg_work_time = round(total_work_time / work_time_count, 1) if work_time_count > 0 else 0.0
    total_ot = round(total_ot, 1)

    if len(all_employee_ids) > 1:
        late_details = f"{late_arrivals_count} late check-ins"
        mispunch_details = f"{mispunch_count} records" if mispunch_count > 0 else "No mispunches"
    else:
        if max_late_minutes > 0 and max_late_date:
            late_details = f"{max_late_minutes} min late ({max_late_date})"
        else:
            late_details = "No late arrivals"
        mispunch_details = f"{mispunch_count} records" if mispunch_count > 0 else "No mispunches"

    days_present_val = int(days_present) if days_present.is_integer() else days_present
    leaves_taken_val = int(leaves_taken) if leaves_taken.is_integer() else leaves_taken

    result = {
        "working_days": working_days,
        "present_count": present_all_count,
        "absent_count": absent_count,
        "leave_count": leave_count,
        "late_arrivals": late_count,
        "mispunches": mispunch_count,
        "avg_work_time": avg_work_time,
        "total_employees": total_employees_count,
        "day_shift_count": day_shift_count,
        "night_shift_count": night_shift_count,
        "present_day_shift": present_day_count,
        "present_night_shift": present_night_count,
        "days_present": days_present_val,
        "leaves_taken": leaves_taken_val,
        "late_details": late_details,
        "mispunch_details": mispunch_details,
        "total_ot": total_ot,
        "breakdown_data": [
            breakdown_present,
            breakdown_leave,
            breakdown_rest,
            breakdown_mispunch,
            breakdown_cl,
        ],
        "kpi_total_employees": total_employees_count,
        "kpi_total_day_shift": day_shift_count,
        "kpi_present_day_shift": present_day_count,
        "kpi_total_night_shift": night_shift_count,
        "kpi_present_night_shift": present_night_count,
        "kpi_absent": absent_count,
        "kpi_on_leave": leave_count,
        "kpi_late_punch": late_count,
    }

    logger.info(
        "Dashboard Summary: Working Days=%s, Present=%s, Absent=%s, "
        "Leave=%s, Late=%s, Day Shift=%s, Night Shift=%s, "
        "Total Employees=%s, Mispunches=%s, Avg Work Time=%s",
        result["working_days"],
        result["present_count"],
        result["absent_count"],
        result["leave_count"],
        result["late_arrivals"],
        result["day_shift_count"],
        result["night_shift_count"],
        result["total_employees"],
        result["mispunches"],
        result["avg_work_time"],
    )

    return result


def fetch_attendance_from_db_from_qs(qs):
    fields = [
        "attendance_date", "employee_id", "employee_name", "in_time", "out_time",
        "working_hours", "card_punch_ot", "shift", "leave_type", "late_minutes", "day",
        "requested_ot", "weekend_ot", "holiday_ot", "ot4", "total_ot_all", "req_overtime", "approved_ot",
        "wt_id", "wt_type_no", "attendance_source", "attendance_status", "mobile", "workday", "weekday"
    ]

    def format_float(val):
        if val is None:
            return ""
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)

    return [
        {
            "Date": r["attendance_date"].strftime("%d-%m-%Y") if r["attendance_date"] else "",
            "Employee ID": r["employee_id"],
            "Employee Name": r["employee_name"],
            "In Time": r["in_time"],
            "Out Time": r["out_time"],
            "Working Hours": format_float(r["working_hours"]),
            "Card Punch OT": format_float(r["card_punch_ot"]),
            "Requested OT": format_float(r["requested_ot"]),
            "Weekend OT": format_float(r["weekend_ot"]),
            "Holiday OT": format_float(r["holiday_ot"]),
            "OT4": format_float(r["ot4"]),
            "Total OT All": format_float(r["total_ot_all"]),
            "Req OverTime": format_float(r["req_overtime"]),
            "Approved OT": format_float(r["approved_ot"]),
            "WT ID": r["wt_id"],
            "WT Type No": r["wt_type_no"],
            "Attendance Source": r["attendance_source"],
            "Day": r["day"],
            "Attendance Status": r["attendance_status"],
            "Shift": r["shift"],
            "Mobile": r["mobile"],
            "Late Minutes": format_float(r["late_minutes"]),
            "Leave Type": r["leave_type"],
            "WorkDay": r["workday"],
            "Weekday": r["weekday"],
        }
        for r in qs.values(*fields)
    ]


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

    is_section_view = (
        scope != "OWN" and not query_employee_id
    )

    # Fetch attendance raw data using the centralized cache service
    attendance = get_attendance(user, query_employee_id or "", start_date, end_date)

    # Filter data based on RBAC rules for normal employees
    if not is_supervisor:
        attendance = [r for r in attendance if r.get("Employee ID") == user.username]

    # Collect the employee IDs from the attendance list to optimize profile loading
    emp_ids = {r.get("Employee ID") for r in attendance if r.get("Employee ID")}
    profiles = {
        p.user.username: p 
        for p in UserProfile.objects.filter(
            user__username__in=emp_ids
        ).select_related("user", "department", "section").all()
    }

    is_section_view = (
        scope != "OWN" and not query_employee_id
    )

    if not is_section_view:
        target_emp_id = query_employee_id if query_employee_id else user.username
        # Find which dates are present in the fetched records
        present_dates = set()
        for r in attendance:
            dt_str = r.get("Date") or r.get("attendance_date")
            dt_obj = parse_date(dt_str)
            if dt_obj:
                present_dates.add(dt_obj.date())
        
        # Determine employee name, shift, day, and mobile to use for virtual records
        emp_name = "—"
        emp_shift = "Day Shift"
        emp_day = "—"
        emp_mobile = "—"
        if attendance:
            sorted_temp = sorted(
                attendance,
                key=lambda x: parse_date(x.get("Date") or x.get("attendance_date")) or datetime.min,
                reverse=True
            )
            emp_name = sorted_temp[0].get("Employee Name") or sorted_temp[0].get("employee_name") or "—"
            emp_shift = sorted_temp[0].get("Shift") or sorted_temp[0].get("shift") or "Day Shift"
            emp_day = sorted_temp[0].get("Day") or sorted_temp[0].get("day") or "—"
            emp_mobile = sorted_temp[0].get("Mobile") or sorted_temp[0].get("mobile") or "—"
        else:
            p = profiles.get(target_emp_id)
            if p:
                emp_name = p.user.get_full_name() or p.user.username
                if p.section:
                    emp_day = p.section.name
                elif p.department:
                    emp_day = p.department.name

        try:
            start_dt_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            start_dt_obj = None
            end_dt_obj = None

        if start_dt_obj and end_dt_obj:
            curr_dt = start_dt_obj
            while curr_dt <= end_dt_obj:
                if curr_dt not in present_dates:
                    # Find shift from the closest actual record by date
                    closest_shift = emp_shift
                    min_diff = None
                    for r in attendance:
                        r_dt = parse_date(r.get("Date") or r.get("attendance_date"))
                        if r_dt:
                            diff = abs((r_dt.date() - curr_dt).days)
                            if min_diff is None or diff < min_diff:
                                min_diff = diff
                                closest_shift = r.get("Shift") or r.get("shift") or emp_shift
                    
                    virtual_rec = {
                        "Employee ID": target_emp_id,
                        "Employee Name": emp_name,
                        "Date": curr_dt.strftime("%d-%m-%Y"),
                        "In Time": "",
                        "Out Time": "",
                        "Working Hours": 0.0,
                        "Card Punch OT": 0.0,
                        "Shift": closest_shift,
                        "Day": emp_day,
                        "Mobile": emp_mobile,
                        "Leave Type": "",
                    }
                    attendance.append(virtual_rec)
                curr_dt += timedelta(days=1)

    # =========================================================================
    # SINGLE SOURCE OF TRUTH: Calculate ALL KPIs from the same filtered dataset
    # =========================================================================
    dashboard_summary = calculate_dashboard_summary(attendance)

    logger.info(
        "KPI Summary: Working Days=%s, Present=%s, Absent=%s, "
        "Leave=%s, Late=%s, Day Shift=%s, Night Shift=%s, "
        "Present Day=%s, Present Night=%s, Total Employees=%s",
        dashboard_summary["working_days"],
        dashboard_summary["present_count"],
        dashboard_summary["absent_count"],
        dashboard_summary["leave_count"],
        dashboard_summary["late_arrivals"],
        dashboard_summary["day_shift_count"],
        dashboard_summary["night_shift_count"],
        dashboard_summary["present_day_shift"],
        dashboard_summary["present_night_shift"],
        dashboard_summary["total_employees"],
    )

    # Build formatted attendance table
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

        shift_raw = str(record.get("Shift") or "").strip()
        is_night_shift = bool(shift_raw) and "Night" in shift_raw
        
        has_in = bool(in_time) and in_time not in ("00:00", "—", "")
        late_minutes = 0.0
        if has_in and ":" in in_time:
            try:
                h, m = map(int, in_time.split(":"))
                wt_id = record.get("WT ID") or record.get("WTID")
                shift_start = get_shift_start_minutes(wt_id, is_night_shift, in_time)
                if h * 60 + m > shift_start:
                    late_minutes = float((h * 60 + m) - shift_start)
            except (ValueError, TypeError):
                pass
        
        if late_minutes == 0:
            try:
                late_minutes = float(record.get("Late Minutes") or 0.0)
            except (ValueError, TypeError):
                late_minutes = 0.0

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

        has_in = bool(in_time) and in_time != "—"
        has_out = bool(out_time) and out_time != "—"

        is_today = date_obj and date_obj.date() == datetime.now().date()
        is_late = late_minutes > 0.0

        if is_holiday:
            if not has_in and not has_out:
                status = "Holiday"
            else:
                status = "Present"
        elif is_today and has_in and not is_late and not has_out:
            status = "Present"
        elif (has_in and not has_out) or (has_out and not has_in):
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
        p = profiles.get(emp_id)
        if p:
            if p.section:
                org_path = p.section.name
            elif p.department:
                org_path = p.department.name
        else:
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
                "late_minutes": late_minutes,
                "wt_id": record.get("WT ID") or record.get("WTID"),
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

    # Build section view stats or employee-specific stats from the SAME dataset
    qs_or_attendance = attendance

    if is_section_view:
        # Use calculate_section_dashboard_stats for its chart/chart data generation
        dashboard_stats = calculate_section_dashboard_stats(
            qs_or_attendance, role_display, section_display, user.username
        )
        # Override the KPI values with our single-source-of-truth calculation
        dashboard_stats["working_days"] = dashboard_summary["working_days"]
        dashboard_stats["days_present"] = dashboard_summary["days_present"]
        dashboard_stats["leaves_taken"] = dashboard_summary["leaves_taken"]
        dashboard_stats["late_arrivals"] = dashboard_summary["late_arrivals"]
        dashboard_stats["mispunches"] = dashboard_summary["mispunches"]
        dashboard_stats["avg_work_time"] = dashboard_summary["avg_work_time"]
        dashboard_stats["total_employees"] = dashboard_summary["total_employees"]
        dashboard_stats["total_ot"] = dashboard_summary["total_ot"]
        dashboard_stats["breakdown_data"] = dashboard_summary["breakdown_data"]
        dashboard_stats["late_details"] = dashboard_summary["late_details"]
        dashboard_stats["mispunch_details"] = dashboard_summary["mispunch_details"]
    else:
        # Use calculate_dashboard_stats for its chart/chart data generation
        dashboard_stats = calculate_dashboard_stats(
            qs_or_attendance, query_employee_id or user.username, start_date, end_date
        )
        # Override the KPI values with our single-source-of-truth calculation
        dashboard_stats["working_days"] = dashboard_summary["working_days"]
        dashboard_stats["days_present"] = dashboard_summary["days_present"]
        dashboard_stats["leaves_taken"] = dashboard_summary["leaves_taken"]
        dashboard_stats["late_arrivals"] = dashboard_summary["late_arrivals"]
        dashboard_stats["mispunches"] = dashboard_summary["mispunches"]
        dashboard_stats["avg_work_time"] = dashboard_summary["avg_work_time"]
        dashboard_stats["total_ot"] = dashboard_summary["total_ot"]
        dashboard_stats["breakdown_data"] = dashboard_summary["breakdown_data"]
        dashboard_stats["late_details"] = dashboard_summary["late_details"]
        dashboard_stats["mispunch_details"] = dashboard_summary["mispunch_details"]

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

    context_dict = {
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
        # Summary row metrics - calculated from the full filtered dataset
        "total_headcount": dashboard_summary["total_employees"],
        "present_today": dashboard_summary["present_count"],
        "absent_today": dashboard_summary["absent_count"],
        "on_leave_today": dashboard_summary["leave_count"],
        "late_punch_today": dashboard_summary["late_arrivals"],
        "pending_tasks_count": pending_tasks_count,
        # Enterprise KPI cards - calculated from the SAME dataset
        "kpi_total_employees": dashboard_summary["kpi_total_employees"],
        "kpi_total_day_shift": dashboard_summary["kpi_total_day_shift"],
        "kpi_present_day_shift": dashboard_summary["kpi_present_day_shift"],
        "kpi_total_night_shift": dashboard_summary["kpi_total_night_shift"],
        "kpi_present_night_shift": dashboard_summary["kpi_present_night_shift"],
        "kpi_absent": dashboard_summary["kpi_absent"],
        "kpi_on_leave": dashboard_summary["kpi_on_leave"],
        "kpi_late_punch": dashboard_summary["kpi_late_punch"],
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



    return context_dict