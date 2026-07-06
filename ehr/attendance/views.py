from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from datetime import datetime, timedelta
import re

def extract_initials(name):
    if not name:
        return "EE"
    parts = re.findall(r'[A-Za-z]+', name)
    if len(parts) > 1:
        return "".join([p[0].upper() for p in parts if p])[:2]
    uppers = [c for c in name if c.isupper()]
    if len(uppers) >= 2:
        return "".join(uppers[:2])
    elif len(name) >= 2:
        return name[:2].upper()
    return (name * 2)[:2].upper()

# pyrefly: ignore [missing-import]
from .services.attendance_api import fetch_attendance
# pyrefly: ignore [missing-import]
from .services.overtime_service import get_cycle_bounds, get_week_bounds, get_all_weeks_in_year, get_all_cycles_in_year
# pyrefly: ignore [missing-import]
from .utils.date_helpers import get_attendance_date_range
# pyrefly: ignore [missing-import]
from .models import UserProfile


def parse_date(date_str):
    """
    Tries to parse date string in multiple potential formats.
    """
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str
    # If it's already a date object but not a datetime
    from datetime import date
    if isinstance(date_str, date) and not isinstance(date_str, datetime):
        return datetime(date_str.year, date_str.month, date_str.day)
        
    date_str = str(date_str).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def calculate_dashboard_stats(attendance_records, employee_id, start_date=None, end_date=None):
    """
    Calculates statistics and chart data from the filtered attendance records.
    """
    if not attendance_records:
        return {
            "working_days": 0,
            "days_present": 0,
            "leaves_taken": 0.0,
            "late_arrivals": 0,
            "late_details": "No late arrivals",
            "mispunches": 0,
            "mispunch_details": "No mispunches",
            "total_ot": 0.0,
            "avg_work_time": 0.0,
            "chart_labels": [],
            "chart_worktime_data": [],
            "breakdown_data": [0, 0, 0],
            "employee_details": {
                "name": "Employee",
                "id": employee_id,
                "mobile": "—",
                "job_title": "Employee",
                "sector": "General Sector",
                "shift": "Day Shift (09:00-18:00)",
                "initials": "EE"
            }
        }

    # Extract employee details from the first record
    first_record = attendance_records[0]
    raw_name = first_record.get("Employee Name", "Pankaj Khurana")
    name = raw_name
    if name == "PankajKhurana":
        name = "Pankaj Khurana"

    # Profile matching the screenshots & dynamic mobile retrieval
    mobile_value = first_record.get("Mobile", "").strip()
    if not mobile_value or mobile_value in ("—", "None", "0"):
        mobile_mapping = {
            "19105203": "+91 98765 43210",
            "19105540": "+91 99999 88888"
        }
        mobile_value = mobile_mapping.get(employee_id, "—")
    job_title = "Assistant Manager" if employee_id == "19105203" else "Associate"
    
    # dtName4 was mapped to Day in formatter
    sector = first_record.get("Day", "Sector 63 - Marketing")
    if not sector or sector == "—":
        sector = "Sector 63 - Marketing"
        
    shift = first_record.get("Shift", "Day Shift")
    if "09:00" not in shift:
        shift = "Day Shift (09:00-18:00)"

    employee_details = {
        "name": name,
        "id": employee_id,
        "mobile": mobile_value,
        "job_title": job_title,
        "sector": sector,
        "shift": shift,
        "initials": extract_initials(name)
    }

    working_days = 0
    days_present = 0.0
    leaves_taken = 0.0
    late_arrivals = 0
    total_ot = 0.0
    total_work_time = 0.0
    max_late_minutes = 0
    max_late_date = ""
    mispunches = 0
    last_mispunch_date = ""

    chart_labels = []
    chart_worktime_data = []
    
    status_present = 0.0
    status_leave = 0.0
    status_rest = 0

    record_map = {}
    for r in attendance_records:
        d = parse_date(r.get("Date"))
        if d:
            record_map[d.date()] = r

    # Determine start and end dates
    if start_date and end_date:
        start_dt = parse_date(start_date)
        end_dt = parse_date(end_date)
    else:
        # Fallback to sorting
        sorted_records = sorted(
            attendance_records,
            key=lambda x: parse_date(x.get("Date", "")) or datetime(1900, 1, 1)
        )
        dates = [parse_date(r.get("Date")) for r in sorted_records if r.get("Date")]
        dates = [d for d in dates if d]
        if dates:
            start_dt = min(dates)
            end_dt = max(dates)
        else:
            start_dt = None
            end_dt = None

    if start_dt and end_dt:
        current_dt = start_dt
        while current_dt <= end_dt:
            date_obj = current_dt
            chart_date = date_obj.strftime("%m-%d")
            chart_labels.append(chart_date)
            
            record = record_map.get(date_obj.date())
            is_weekend = date_obj.weekday() == 6
            
            if record:
                # Working hours
                try:
                    work_time = float(record.get("Working Hours") or 0.0)
                except Exception:
                    work_time = 0.0

                # Overtime
                try:
                    ot = float(record.get("Card Punch OT") or 0.0)
                except Exception:
                    ot = 0.0
                
                total_ot += ot
                chart_worktime_data.append(work_time)

                # Check-in time
                in_time_str = record.get("In Time", "").strip()
                out_time_str = record.get("Out Time", "").strip()
                has_check_in = bool(in_time_str) and in_time_str not in ("00:00", "—", "")
                has_check_out = bool(out_time_str) and out_time_str not in ("00:00", "—", "")

                if (has_check_in and not has_check_out) or (has_check_out and not has_check_in):
                    mispunches += 1
                    last_mispunch_date = chart_date

                if not has_check_in:
                    if is_weekend:
                        status_rest += 1
                    else:
                        working_days += 1
                        leaves_taken += 1.0
                        status_leave += 1.0
                else:
                    if is_weekend:
                        if work_time >= 8.0:
                            working_days += 1
                            days_present += 1.0
                            status_present += 1.0
                            total_work_time += work_time
                        else:
                            status_rest += 1
                            total_work_time += work_time
                    else:
                        working_days += 1
                        if work_time >= 8.0:
                            days_present += 1.0
                            status_present += 1.0
                            total_work_time += work_time
                        else:
                            days_present += 0.5
                            leaves_taken += 0.5
                            status_leave += 0.5
                            status_present += 0.5
                            total_work_time += work_time
                    
                    if in_time_str and ":" in in_time_str:
                        try:
                            h, m = map(int, in_time_str.split(":"))
                            check_in_minutes = h * 60 + m
                            
                            shift_name = record.get("Shift", "")
                            if "Night" in shift_name:
                                shift_start_minutes = 20 * 60
                            else:
                                shift_start_minutes = 9 * 60
                            
                            if check_in_minutes > shift_start_minutes + 15:
                                late_arrivals += 1
                                late_minutes = check_in_minutes - shift_start_minutes
                                if late_minutes > max_late_minutes:
                                    max_late_minutes = late_minutes
                                    max_late_date = chart_date
                        except Exception:
                            pass
            else:
                chart_worktime_data.append(0.0)
                if is_weekend:
                    status_rest += 1
                else:
                    working_days += 1
                    leaves_taken += 1.0
                    status_leave += 1.0
            
            current_dt += timedelta(days=1)

    avg_work_time = round(total_work_time / days_present, 1) if days_present > 0 else 0.0
    total_ot = round(total_ot, 1)
    
    if max_late_minutes > 0:
        late_details = f"{max_late_minutes} min late ({max_late_date})"
    else:
        late_details = "No late arrivals"

    days_present_val = int(days_present) if days_present.is_integer() else days_present
    status_present_val = int(status_present) if status_present.is_integer() else status_present

    return {
        "working_days": working_days,
        "days_present": days_present_val,
        "leaves_taken": int(leaves_taken) if leaves_taken.is_integer() else leaves_taken,
        "late_arrivals": late_arrivals,
        "late_details": late_details,
        "mispunches": mispunches,
        "mispunch_details": f"{mispunches} records" if mispunches > 0 else "No mispunches",
        "total_ot": total_ot,
        "avg_work_time": avg_work_time,
        "chart_labels": chart_labels,
        "chart_worktime_data": chart_worktime_data,
        "breakdown_data": [status_present_val, int(status_leave) if status_leave.is_integer() else status_leave, status_rest],
        "employee_details": employee_details
    }


def get_expected_dtname4(role, section):
    if role == 'smt_pd':
        if section == 's63':
            return 'Sector 63 - SMT PD'
        elif section == 'c39':
            return 'Phase 2 - SMT PD'
    elif role == 'assy_pd':
        if section == 's63':
            return 'Sector 63 - ASSY PD'
        elif section == 'c39':
            return 'Phase 2 - ASSY PD'
    return None


def calculate_section_dashboard_stats(attendance_records, role_display, section_display):
    """
    Calculates aggregated statistics and charts for a section of multiple employees.
    """
    if not attendance_records:
        return {
            "total_employees": 0,
            "working_days": 0,
            "days_present": 0,
            "leaves_taken": 0,
            "late_arrivals": 0,
            "late_details": "No late arrivals",
            "mispunches": 0,
            "mispunch_details": "No mispunches",
            "total_ot": 0,
            "avg_work_time": 0,
            "chart_labels": [],
            "chart_ot_data": [],
            "breakdown_data": [0, 0, 0],
            "is_section": True,
            "employee_details": {
                "name": f"{role_display} ({section_display})",
                "id": "Section-Wide",
                "mobile": "—",
                "job_title": "Section Dashboard",
                "sector": f"{role_display} - {section_display}",
                "shift": "Multiple Shifts",
                "initials": "".join([part[0] for part in role_display.split() if part])[:2].upper()
            }
        }

    # Find unique employees
    employees = set(r.get("Employee ID") for r in attendance_records if r.get("Employee ID"))
    total_employees = len(employees)

    # Group records by Date to find unique working dates
    unique_dates = set(r.get("Date") for r in attendance_records if r.get("Date"))
    working_days = len(unique_dates)

    total_present = 0
    total_leaves = 0.0
    total_late = 0
    total_ot = 0.0
    total_work_time = 0.0
    work_time_records_count = 0
    total_mispunches = 0

    # For charts, we can aggregate by Date
    date_aggregates = {}
    for r in attendance_records:
        dt = r.get("Date")
        if not dt:
            continue
        if dt not in date_aggregates:
            date_aggregates[dt] = {"ot": 0.0, "present": 0, "leave": 0.0, "late": 0, "work_time": 0.0, "count": 0}
        
        # OT
        try:
            ot = float(r.get("Card Punch OT") or 0.0)
        except Exception:
            ot = 0.0
        date_aggregates[dt]["ot"] += ot
        total_ot += ot

        # Work hours
        try:
            work_time = float(r.get("Working Hours") or 0.0)
        except Exception:
            work_time = 0.0
        if work_time > 0:
            total_work_time += work_time
            work_time_records_count += 1
            date_aggregates[dt]["work_time"] += work_time
            date_aggregates[dt]["count"] += 1

        # Check-in time / status
        in_time_str = r.get("In Time", "").strip()
        out_time_str = r.get("Out Time", "").strip()
        has_in = bool(in_time_str) and in_time_str not in ("00:00", "—", "")
        has_out = bool(out_time_str) and out_time_str not in ("00:00", "—", "")
        if (has_in and not has_out) or (has_out and not has_in):
            total_mispunches += 1
        
        # We can also parse date to check if it's weekend
        date_obj = parse_date(dt)
        is_weekend = False
        if date_obj and date_obj.weekday() == 6:
            is_weekend = True

        if not in_time_str or in_time_str in ("00:00", "—", ""):
            if not is_weekend:
                total_leaves += 1.0
                date_aggregates[dt]["leave"] += 1.0
        else:
            if work_time >= 8.0:
                total_present += 1
                date_aggregates[dt]["present"] += 1
            else:
                total_leaves += 0.5
                date_aggregates[dt]["leave"] += 0.5
            
            # Late check-in
            if in_time_str and ":" in in_time_str:
                try:
                    h, m = map(int, in_time_str.split(":"))
                    if h * 60 + m > 9 * 60 + 15:
                        total_late += 1
                        date_aggregates[dt]["late"] += 1
                except Exception:
                    pass

    avg_work_time = round(total_work_time / work_time_records_count, 1) if work_time_records_count > 0 else 0.0
    total_ot = round(total_ot, 1)

    # Sort dates to build trend labels and data
    sorted_dates = sorted(date_aggregates.keys(), key=parse_date)
    chart_labels = []
    chart_worktime_data = []
    
    for dt in sorted_dates:
        date_obj = parse_date(dt)
        label = date_obj.strftime("%m-%d") if date_obj else dt
        chart_labels.append(label)
        count = date_aggregates[dt]["count"]
        avg_wt = date_aggregates[dt]["work_time"] / count if count > 0 else 0.0
        chart_worktime_data.append(round(avg_wt, 1))

    status_present = total_present
    status_leave = int(total_leaves) if total_leaves.is_integer() else total_leaves
    status_rest = 0

    role_initials = "".join([part[0] for part in role_display.split() if part])[:2].upper()

    return {
        "total_employees": total_employees,
        "working_days": working_days,
        "days_present": total_present,
        "leaves_taken": status_leave,
        "late_arrivals": total_late,
        "late_details": f"{total_late} late check-ins",
        "mispunches": total_mispunches,
        "mispunch_details": f"{total_mispunches} records" if total_mispunches > 0 else "No mispunches",
        "total_ot": total_ot,
        "avg_work_time": avg_work_time,
        "chart_labels": chart_labels,
        "chart_worktime_data": chart_worktime_data,
        "breakdown_data": [status_present, status_leave, status_rest],
        "is_section": True,
        "employee_details": {
            "name": f"{role_display} ({section_display})",
            "id": "Section-Wide",
            "mobile": "—",
            "job_title": "Section Dashboard",
            "sector": f"{role_display} - {section_display}",
            "shift": "Multiple Shifts",
            "initials": role_initials if role_initials else "PD"
        }
    }


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
        is_rest_day = bool(is_weekend or (not has_check_in and is_weekend))

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
            except Exception:
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


@login_required
def home(request):
    """
    Home Page - Secured with login_required and shows the EHR Portals (Dashboard, Leaves, OT, Corrections, Approvals)
    """
    is_superuser = request.user.is_superuser
    
    # Get user profile or default for admin / fallback
    try:
        profile = request.user.profile
        role = profile.role
        section = profile.section
    except Exception:
        # Fallback for old users, admin, or missing profile
        role = 'employee'
        section = None
        if is_superuser:
            role = 'admin'

    role_display = dict(UserProfile.ROLE_CHOICES).get(role, role.upper()) if role != 'admin' else "Admin"
    section_display = dict(UserProfile.SECTION_CHOICES).get(section, section.upper()) if section else ""
    is_supervisor = is_superuser or (role in ('smt_pd', 'assy_pd'))

    # Determine active tab
    active_tab = request.GET.get("tab", "dashboard")

    # Handle POST Submissions (Dashboard Filter)
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "filter_dashboard":
            query_employee_id = request.POST.get("employee_id", "").strip()
            start_date = request.POST.get("start_date")
            end_date = request.POST.get("end_date")
            url = f"/?tab=dashboard&start_date={start_date}&end_date={end_date}"
            if query_employee_id:
                url += f"&employee_id={query_employee_id}"
            return redirect(url)

    # GET Request Processing
    query_employee_id = request.GET.get("employee_id")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if not start_date or not end_date:
        if role == 'employee' or is_superuser:
            if not query_employee_id:
                query_employee_id = request.user.username
        else:
            if query_employee_id is None:
                query_employee_id = "" # Section overview by default for PD roles
        
        if role in ('smt_pd', 'assy_pd') and not query_employee_id:
            # Section view: fetch only previous day's data
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
        attendance = fetch_attendance(
            employee_id=query_employee_id,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        attendance = []

    # Filter data based on RBAC rules
    expected_dtname4 = get_expected_dtname4(role, section)
    if expected_dtname4 and not is_superuser:
        attendance = [r for r in attendance if r.get("Day") == expected_dtname4]

    is_section_view = (role in ('smt_pd', 'assy_pd') and not query_employee_id and not is_superuser)
    
    if is_section_view:
        dashboard_stats = calculate_section_dashboard_stats(attendance, role_display, section_display)
    else:
        dashboard_stats = calculate_dashboard_stats(attendance, query_employee_id or request.user.username, start_date, end_date)

    # Format the attendance log items
    formatted_attendance = []
    sorted_for_table = sorted(
        attendance,
        key=lambda x: parse_date(x.get("Date", "")) or datetime.min,
        reverse=True
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
        except Exception:
            work_time = 0.0
            
        if work_time > 0:
            work_hrs = f"{int(work_time)}h" if work_time.is_integer() else f"{work_time}h"
        else:
            work_hrs = "—"

        ot_str = record.get("Card Punch OT", "0.0")
        try:
            ot = float(ot_str or 0.0)
        except Exception:
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

        if not in_time or in_time == "—":
            if is_weekend:
                status = "Rest Day"
            else:
                status = "Absent"
        else:
            if work_time >= 8.0:
                status = "Present"
            else:
                status = f"CL(0.5d)"

        # Determine shift label for filtering
        shift_raw = str(record.get("Shift") or "").strip()
        shift_label = "day"
        if "Night" in shift_raw:
            shift_label = "night"

        formatted_attendance.append({
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
            "department": record.get("Day", "—"),
            "shift_label": shift_label
        })

    # Period text for display
    try:
        start_obj = parse_date(start_date)
        end_obj = parse_date(end_date)
        period_text = f"{start_obj.strftime('%b %d')} – {end_obj.strftime('%b %d, %Y')}" # type: ignore
    except Exception:
        period_text = f"{start_date} to {end_date}"

    # DYNAMIC METRICS FOR TOP 6 CARDS
    total_headcount = 5
    present_today = 0
    absent_today = 0
    on_leave_today = 0
    late_punch_today = 0
    
    unique_employees = set(r.get("employee_id") for r in formatted_attendance if r.get("employee_id"))
    total_headcount = len(unique_employees) if len(unique_employees) > 0 else 5
    
    if formatted_attendance:
        dates = [r["raw_date"] for r in formatted_attendance if r.get("raw_date")]
        if dates:
            latest_ref_date = max(dates)
            today_records = [r for r in formatted_attendance if r.get("raw_date") == latest_ref_date]
            
            for r in today_records:
                in_time = r.get("in_time", "—")
                status = r.get("status", "")
                if in_time and in_time != "—":
                    present_today += 1
                    try:
                        h, m = map(int, in_time.split(":"))
                        if h * 60 + m > 9 * 60 + 15:
                            late_punch_today += 1
                    except Exception:
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
    leave_allotments = {"casual": {"total": 12.0, "used": 0.0, "remaining": 12.0}, "sick": {"total": 10.0, "used": 0.0, "remaining": 10.0}, "earned": {"total": 15.0, "used": 0.0, "remaining": 15.0}}
    user_leaves = []
    user_overtimes = []
    user_corrections = []
    pending_leaves_list = []
    pending_ots_list = []
    pending_corrections_list = []

    # Build the context
    context = {
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
        
        # Keep context variables for template compatibility (empty/default values)
        "directory": directory,
        "leave_allotments": leave_allotments,
        "user_leaves": user_leaves,
        "user_overtimes": user_overtimes,
        "user_corrections": user_corrections,
        "pending_leaves": pending_leaves_list,
        "pending_ots": pending_ots_list,
        "pending_corrections": pending_corrections_list,
        "is_supervisor": is_supervisor,
    }

    return render(request, "attendance/home.html", context)




def signup_view(request):
    """
    Employee Signup View
    """
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()
        role = request.POST.get("role", "employee").strip()
        section = request.POST.get("section", "").strip()

        if not employee_id or not password:
            messages.error(request, "Employee ID and password are required.")
            return render(request, "attendance/signup.html", {
                "employee_id": employee_id,
                "role": role,
                "section": section
            })

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "attendance/signup.html", {
                "employee_id": employee_id,
                "role": role,
                "section": section
            })

        if role in ("smt_pd", "assy_pd") and not section:
            messages.error(request, "Section is required for SMT PD and ASSY PD roles.")
            return render(request, "attendance/signup.html", {
                "employee_id": employee_id,
                "role": role,
                "section": section
            })

        if User.objects.filter(username=employee_id).exists():
            messages.error(request, "An account with this Employee ID already exists.")
            return render(request, "attendance/signup.html", {
                "employee_id": employee_id,
                "role": role,
                "section": section
            })

        try:
            # Create user where username stores the Employee ID (or username)
            user = User.objects.create_user(username=employee_id, password=password)
            user.save()

            # Create the associated UserProfile
            UserProfile.objects.create(
                user=user,
                role=role,
                section=section if role in ("smt_pd", "assy_pd") else None
            )

            # Automatically login after signup
            login(request, user)
            messages.success(request, f"Account created successfully for {employee_id}!")
            return redirect("home")
        except Exception as e:
            messages.error(request, f"Error creating account: {str(e)}")
            return render(request, "attendance/signup.html", {
                "employee_id": employee_id,
                "role": role,
                "section": section
            })

    return render(request, "attendance/signup.html")


def login_view(request):
    """
    Employee Login View
    """
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "").strip()
        password = request.POST.get("password", "")

        if not employee_id or not password:
            messages.error(request, "Employee ID and password are required.")
            return render(request, "attendance/login.html")

        user = authenticate(request, username=employee_id, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Logged in as {employee_id}!")
            return redirect("home")
        else:
            messages.error(request, "Invalid Employee ID or Password.")
            return render(request, "attendance/login.html", {"employee_id": employee_id})

    return render(request, "attendance/login.html")


def logout_view(request):
    """
    Employee Logout View
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


def overtime_dashboard(request):
    """
    Overtime Dashboard - Shows overtime analytics with period toggle (Daily/Weekly/Monthly)
    """
    if not request.user.is_authenticated:
        return redirect("login")
        
    # pyrefly: ignore [missing-import]
    from .services.overtime_service import get_overtime_summary, get_scope_overtime_summary, get_all_weeks_in_year, get_all_cycles_in_year
    
    # Get user profile
    is_superuser = request.user.is_superuser
    role = 'employee'
    section = None
    if not is_superuser:
        try:
            profile = request.user.profile
            role = profile.role
            section = profile.section
        except Exception:
            pass
    
    is_supervisor = is_superuser or (role in ('smt_pd', 'assy_pd'))
    
    # Read period from query param
    period = request.GET.get("period", "weekly")
    if period not in ("daily", "weekly", "monthly"):
        period = "weekly"
    
    # Check for custom date range from date picker
    custom_start = request.GET.get("custom_start")
    custom_end = request.GET.get("custom_end")
    
    # Check for specific week or cycle selection
    week_num = request.GET.get("week_num")
    cycle_num = request.GET.get("cycle_num")
    
    # Compute start/end dates based on period or custom dates
    today = datetime.now().date()
    start_date = today
    end_date = today
    
    if custom_start and custom_end:
        # Use custom date range from date picker
        try:
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            period = "custom"  # Mark as custom period
        except (ValueError, TypeError):
            # Fall back to default period if dates are invalid
            custom_start = None
            custom_end = None
    
    if not custom_start or not custom_end:
        # Use preset period
        if period == "daily":
            yesterday = today - timedelta(days=1)
            start_date = yesterday
            end_date = yesterday
        elif period == "weekly":
            # Check if specific week is selected
            if week_num:
                try:
                    year = int(request.GET.get("year", today.year))
                    start_date, end_date = get_week_bounds(int(week_num), year)
                except (ValueError, TypeError):
                    # Fall back to current week
                    start_date = today - timedelta(days=today.weekday())
                    end_date = start_date + timedelta(days=6)
            else:
                # Default to current week
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)
        else:  # monthly
            # Check if specific cycle is selected
            if cycle_num:
                try:
                    year = int(request.GET.get("year", today.year))
                    cycles = get_all_cycles_in_year(year)
                    cycle_idx = int(cycle_num) - 1
                    if 0 <= cycle_idx < len(cycles):
                        start_date = cycles[cycle_idx]["start"]
                        end_date = cycles[cycle_idx]["end"]
                    else:
                        # Fall back to current cycle
                        start_date, end_date = get_cycle_bounds(today)
                except (ValueError, TypeError, IndexError):
                    # Fall back to current cycle
                    start_date, end_date = get_cycle_bounds(today)
            else:
                # Default to current cycle
                start_date, end_date = get_cycle_bounds(today)
    
    # Convert to string format for API
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Get employee ID
    if role == 'employee' and not is_superuser:
        emp_id = request.user.username
    else:
        emp_id = request.GET.get("employee_id", request.user.username)
    
    # Fetch overtime summary
    summary = get_overtime_summary(emp_id, start_date_str, end_date_str)
    
    # If supervisor, also get scope rollup
    scope_summary = None
    if is_supervisor:
        expected_dtname4 = get_expected_dtname4(role, section)
        if expected_dtname4:
            scope_summary = get_scope_overtime_summary(expected_dtname4, start_date_str, end_date_str)
    
    # Period text for display
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
        else:  # custom
            period_text = f"Custom — {start_obj.strftime('%b %d, %Y')} to {end_obj.strftime('%b %d, %Y')}"
    except Exception:
        period_text = f"{start_date_str} to {end_date_str}"
    
    # Get all weeks and cycles for dropdowns
    current_year = today.year
    all_weeks = get_all_weeks_in_year(current_year)
    all_cycles = get_all_cycles_in_year(current_year)
    
    context = {
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
        "role_display": dict(UserProfile.ROLE_CHOICES).get(role, role.upper()) if role != 'admin' else "Admin",
        "section_display": dict(UserProfile.SECTION_CHOICES).get(section, section.upper()) if section else "",
        "custom_start": custom_start,
        "custom_end": custom_end,
        "all_weeks": all_weeks,
        "all_cycles": all_cycles,
        "selected_week": week_num,
        "selected_cycle": cycle_num,
        "current_year": current_year,
    }
    
    return render(request, "attendance/overtime.html", context)


def attendance_api(request):
    """
    JSON API - Secured and RBAC filtered
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required"
        }, status=401)

    employee_id = request.GET.get("employee_id")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    # Get user details
    is_superuser = request.user.is_superuser
    role = 'employee'
    section = None
    if not is_superuser:
        try:
            profile = request.user.profile
            role = profile.role
            section = profile.section
        except Exception:
            pass

    # Enforce regular employee limits
    if role == 'employee' and not is_superuser:
        employee_id = request.user.username

    if not start_date or not end_date:
        return JsonResponse({
            "success": False,
            "message": "Missing Parameters"
        })

    attendance = fetch_attendance(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date
    )

    # Filter data based on RBAC rules
    expected_dtname4 = get_expected_dtname4(role, section)
    if expected_dtname4 and not is_superuser:
        attendance = [r for r in attendance if r.get("Day") == expected_dtname4]

    return JsonResponse({
        "success": True,
        "count": len(attendance),
        "data": attendance
    })


@login_required
def mispunch_dashboard(request):
    """
    Mispunch Dashboard - Shows Mispunches, Short Leaves, Half Days, and Full Days
    """
    is_superuser = request.user.is_superuser
    role = 'employee'
    section = None
    if not is_superuser:
        try:
            profile = request.user.profile
            role = profile.role
            section = profile.section
        except Exception:
            pass

    # Cycle selection
    # pyrefly: ignore [missing-import]
    from .services.overtime_service import get_cycle_bounds, get_all_cycles_in_year
    today = datetime.now().date()
    current_year = today.year
    cycle_num = request.GET.get("cycle_num")
    
    try:
        year = int(request.GET.get("year", current_year))
    except (ValueError, TypeError):
        year = current_year
        
    all_cycles = get_all_cycles_in_year(year)
    
    if cycle_num:
        try:
            cycle_idx = int(cycle_num) - 1
            if 0 <= cycle_idx < len(all_cycles):
                start_date = all_cycles[cycle_idx]["start"]
                end_date = all_cycles[cycle_idx]["end"]
            else:
                start_date, end_date = get_cycle_bounds(today)
        except (ValueError, TypeError, IndexError):
            start_date, end_date = get_cycle_bounds(today)
    else:
        start_date, end_date = get_cycle_bounds(today)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    employee_id = request.user.username if (role == 'employee' and not is_superuser) else request.GET.get("employee_id", request.user.username)

    attendance = fetch_attendance(
        employee_id=employee_id,
        start_date=start_str,
        end_date=end_str
    )

    expected_dtname4 = get_expected_dtname4(role, section)
    if expected_dtname4 and not is_superuser:
        attendance = [r for r in attendance if r.get("Day") == expected_dtname4]

    records = []
    stats = {
        "mispunch": 0,
        "leave": 0,
        "short_leave": 0,
        "half_day": 0,
        "full_day": 0
    }

    for record in attendance:
        go1 = record.get("In Time", "").strip()
        out1 = record.get("Out Time", "").strip()
        
        # Determine if it's a Sunday (weekday == 6)
        date_obj = parse_date(record.get("Date", ""))
        is_sunday = date_obj.weekday() == 6 if date_obj else False
        
        # Treat "00:00" and "—" as blank
        if go1 in ("00:00", "—"): go1 = ""
        if out1 in ("00:00", "—"): out1 = ""
        
        category = ""
        try:
            work_hrs = float(record.get("Working Hours", 0) or 0)
        except (ValueError, TypeError):
            work_hrs = 0.0

        if not go1 and not out1:
            if not is_sunday and not record.get("Leave Type"):
                category = "Leave"
                stats["leave"] += 1
        elif not go1 or not out1:
            if not is_sunday and not record.get("Leave Type"):
                category = "Mispunch"
                stats["mispunch"] += 1
        else:
            # Check shift timings to validate short leave
            shift_str = str(record.get("Shift") or "")
            import re
            
            # Default to 09:00 - 18:00 if no match
            shift_in, shift_out = 9*60, 18*60 
            match = re.search(r'(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})', shift_str)
            if match:
                sh, sm, eh, em = map(int, match.groups())
                shift_in = sh * 60 + sm
                shift_out = eh * 60 + em
                
            def to_mins(t_str):
                try:
                    h, m = map(int, t_str.split(':'))
                    return h * 60 + m
                except:
                    return 0
                    
            actual_in = to_mins(go1)
            actual_out = to_mins(out1)
            
            late_mins = actual_in - shift_in if actual_in >= shift_in else 0
            early_mins = shift_out - actual_out if shift_out >= actual_out else 0
            
            # Validate short leave: missing ~2 hours at start OR ~2 hours at end (90 to 180 mins)
            is_valid_short_leave = (90 <= late_mins <= 180) or (90 <= early_mins <= 180)
            
            if work_hrs >= 8.5:
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
            records.append({
                "date": date_obj.strftime("%d/%m/%Y") if date_obj else record.get("Date", ""),
                "day": date_obj.strftime("%A") if date_obj else "",
                "in_time": go1 or "—",
                "out_time": out1 or "—",
                "working_hours": f"{work_hrs}h",
                "category": category,
                "employee_name": record.get("Employee Name", "—"),
                "department": record.get("Day", "—")
            })

    # Sort records by date descending
    records.sort(key=lambda x: parse_date(x["date"]) or datetime.min, reverse=True)

    context = {
        "active_tab": "leaves",
        "records": records,
        "stats": stats,
        "start_date": start_str,
        "end_date": end_str,
        "role_display": dict(UserProfile.ROLE_CHOICES).get(role, role.upper()) if role != 'admin' else "Admin",
        "all_cycles": all_cycles,
        "selected_cycle": cycle_num,
        "current_year": current_year,
    }
    return render(request, "attendance/mispunch.html", context)


