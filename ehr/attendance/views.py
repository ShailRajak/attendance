from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from attendance.services.auth_service import (
    authenticate_user,
    login_user,
    logout_user,
    register_user,
    validate_signup,
)
from attendance.services.api_service import get_attendance_api_data
from attendance.services.dashboard_service import get_home_dashboard_data
from attendance.services.overtime_service import get_overtime_dashboard_data
from attendance.services.leaves_service import get_leaves_dashboard_data
from attendance.services.pwa_service import get_pwa_manifest, get_pwa_service_worker
from attendance.utils.date_helpers import get_shift_start_minutes


@login_required
def home(request):
    """
    Home Page - Secured with login_required and shows the EHR Portals (Dashboard, Leaves, OT, Corrections, Approvals)
    """
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
    active_tab = request.GET.get("tab", "dashboard")

    # Delegate to Service Layer
    context = get_home_dashboard_data(
        user=request.user,
        start_date=start_date,
        end_date=end_date,
        query_employee_id=query_employee_id,
        active_tab=active_tab,
    )

    return render(request, "attendance/home.html", context)


def signup_view(request):
    """
    Employee Signup View
    """
    from attendance.models import Role, Company, Plant, Department, Section, Team

    if request.user.is_authenticated:
        return redirect("home")

    # Exclude roles with 'ALL' data scope to prevent administrative self-promotion
    roles = Role.objects.filter(is_active=True).exclude(data_scope="ALL").order_by("name")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()
        role = request.POST.get("role", "").strip()
        company = "ismartu"
        plant = request.POST.get("plant", "").strip()
        department = ""
        section = request.POST.get("section", "").strip()
        team = request.POST.get("team", "").strip()

        # Validate using Auth Service
        is_valid, error_msg = validate_signup(
            employee_id, password, confirm_password, role, company, plant, department, section, team
        )
        if not is_valid:
            messages.error(request, error_msg)
            return render(
                request,
                "attendance/signup.html",
                {
                    "employee_id": employee_id,
                    "role": role,
                    "company": company,
                    "plant": plant,
                    "department": department,
                    "section": section,
                    "team": team,
                    "roles": roles,
                },
            )

        # Register using Auth Service
        user, error_msg = register_user(employee_id, password, role, company, plant, department, section, team)
        if error_msg:
            messages.error(request, f"Error creating account: {error_msg}")
            return render(
                request,
                "attendance/signup.html",
                {
                    "employee_id": employee_id,
                    "role": role,
                    "company": company,
                    "plant": plant,
                    "department": department,
                    "section": section,
                    "team": team,
                    "roles": roles,
                },
            )

        # Log in and redirect
        login_user(request, user)
        messages.success(
            request, f"Account created successfully for {employee_id}!"
        )
        return redirect("home")

    return render(
        request,
        "attendance/signup.html",
        {"roles": roles},
    )


def login_view(request):
    """
    Employee Login View
    """
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "").strip()
        password = request.POST.get("password", "")

        # Authenticate using Auth Service
        user, error_msg = authenticate_user(request, employee_id, password)
        if user is not None:
            login_user(request, user)
            return redirect("home")
        else:
            messages.error(request, error_msg)
            return render(
                request, "attendance/login.html", {"employee_id": employee_id}
            )

    return render(request, "attendance/login.html")


def logout_view(request):
    """
    Employee Logout View
    """
    logout_user(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


def overtime_dashboard(request):
    """
    Overtime Dashboard - Shows overtime analytics with period toggle (Daily/Weekly/Monthly)
    """
    if not request.user.is_authenticated:
        return redirect("login")

    # Delegate to Service Layer
    context = get_overtime_dashboard_data(user=request.user, get_params=request.GET)

    return render(request, "attendance/overtime.html", context)


def attendance_api(request):
    """
    JSON API - Secured and RBAC filtered
    """
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "message": "Authentication required"}, status=401
        )

    # Delegate to API Service
    success, data, status_code = get_attendance_api_data(
        user=request.user, get_params=request.GET
    )
    return JsonResponse(data, status=status_code)


@login_required
def leaves_dashboard(request):
    """
    Leaves Dashboard - Shows Mispunches, Short Leaves, Half Days, and Full Days
    """
    # Delegate to Leaves Service Layer
    context = get_leaves_dashboard_data(
        user=request.user,
        period=request.GET.get("period"),
        cycle_num=request.GET.get("cycle_num"),
        week_num=request.GET.get("week_num"),
        year=request.GET.get("year"),
        query_employee_id=request.GET.get("employee_id"),
    )
    return render(request, "attendance/leaves.html", context)


def pwa_service_worker(request):
    """
    Serves sw.js service worker.
    """
    # Delegate to PWA Service
    content, content_type = get_pwa_service_worker()
    return HttpResponse(content, content_type=content_type)


def pwa_manifest(request):
    """
    Serves manifest.json.
    """
    # Delegate to PWA Service
    content, content_type = get_pwa_manifest()
    return HttpResponse(content, content_type=content_type)


def offline_view(request):
    """
    Offline view fallback.
    """
    return render(request, "attendance/offline.html")


@login_required
def submit_feedback(request):
    """
    Allows employees to submit feedback, or allows superusers to view all feedback.
    """
    from attendance.models import Feedback

    if request.user.is_superuser:
        feedbacks = Feedback.objects.all().order_by("-date")
        context = {
            "active_tab": "feedback",
            "feedbacks": feedbacks,
        }
        return render(request, "attendance/feedback.html", context)

    # Resolve default plant from user profile
    default_plant = "S63"
    if hasattr(request.user, "profile") and request.user.profile.plant:
        plant_code = request.user.profile.plant.code.upper()
        if "C39" in plant_code:
            default_plant = "C39"
        else:
            default_plant = "S63"

    if request.method == "POST":
        feedback_text = request.POST.get("feedback", "").strip()
        plant = request.POST.get("plant", default_plant).strip()

        if not feedback_text:
            messages.error(request, "Feedback text cannot be empty.")
        else:
            Feedback.objects.create(
                employee_id=request.user.username,
                plant=plant,
                feedback=feedback_text
            )
            messages.success(request, "Thank you! Your feedback has been submitted successfully.")
            return redirect("home")

    context = {
        "active_tab": "feedback",
        "default_plant": default_plant,
        "employee_id": request.user.username,
    }
    return render(request, "attendance/feedback.html", context)


@login_required
def attendance_drilldown_api(request):
    """
    API for interactive chart drill-down. Filters data based on active filters and the clicked chart category.
    """
    from datetime import datetime
    from django.db import models
    from attendance.models import AttendanceRecord, OvertimeLimitConfig
    from attendance.services.rbac_service import RBACService
    from attendance.services.overtime_service import get_scope_overtime_summary

    # 1. Enforce RBAC bounds and resolve user scope
    accessible_users = set(
        RBACService.get_accessible_employees(request.user).values_list("user__username", flat=True)
    )
    scope = RBACService.get_scope(request.user)
    is_superuser = request.user.is_superuser
    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

    # Determine target employee ID
    employee_id = request.GET.get("employee_id", "").strip()
    if employee_id and employee_id != request.user.username and not is_supervisor:
        return JsonResponse({"success": False, "error": "Unauthorized employee ID filter"}, status=403)

    if not is_supervisor:
        target_emp_id = request.user.username
    else:
        target_emp_id = employee_id

    # 2. Extract and validate parameters
    start_date_str = request.GET.get("start_date", "").strip()
    end_date_str = request.GET.get("end_date", "").strip()
    filter_type = request.GET.get("filter_type", "").strip()
    filter_value = request.GET.get("filter_value", "").strip()

    # Allowlist validation
    ALLOWED_FILTER_TYPES = ['attendance_status', 'date', 'late', 'leave_type', 'overtime_level', 'department', 'section']
    if filter_type not in ALLOWED_FILTER_TYPES:
        return JsonResponse({"success": False, "error": "Invalid filter type"}, status=400)

    # Date parsing
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            from attendance.utils.date_helpers import get_attendance_date_range
            start_dt, _ = get_attendance_date_range()
            start_date = start_dt.date() if isinstance(start_dt, datetime) else start_dt

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            from attendance.utils.date_helpers import get_attendance_date_range
            _, end_dt = get_attendance_date_range()
            end_date = end_dt.date() if isinstance(end_dt, datetime) else end_dt
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date format"}, status=400)

    # 3. Handle overtime_level filtering (returns early)
    from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4
    role, section = resolve_user_role_and_section(request.user)
    expected_dtname4 = get_expected_dtname4(role, section, request.user.username)

    if filter_type == "overtime_level":
        ot_config = OvertimeLimitConfig.load()
        low_limit = ot_config.ot_low_limit
        medium_limit = ot_config.ot_medium_limit
        is_all_scope = is_superuser or scope == "ALL"

        scope_summary = get_scope_overtime_summary(
            request.user,
            accessible_usernames=accessible_users,
            start_date=start_date_str,
            end_date=end_date_str,
            expected_dtname4=expected_dtname4,
            is_all_scope=is_all_scope
        )
        employees = scope_summary.get("employees", [])

        filtered_employees = []
        for emp in employees:
            tot = float(emp.get("total_ot") or 0.0)
            if filter_value == "Low" and tot < low_limit:
                filtered_employees.append(emp)
            elif filter_value == "Medium" and low_limit <= tot <= medium_limit:
                filtered_employees.append(emp)
            elif filter_value == "High" and tot > medium_limit:
                filtered_employees.append(emp)

        return JsonResponse({
            "success": True,
            "filter_type": filter_type,
            "filter_value": filter_value,
            "count": len(filtered_employees),
            "records": filtered_employees
        })

    # 4. Fetch attendance data from centralized service
    from attendance.services.attendance_service import get_attendance
    from attendance.management.commands.sync_attendance import safe_float
    from datetime import date

    section_param = request.GET.get("section", "").strip()
    fetch_emp_id = target_emp_id if target_emp_id else ""
    attendance = get_attendance(request.user, fetch_emp_id, start_date, end_date)

    from attendance.models import UserProfile
    emp_ids = {r.get("Employee ID") for r in attendance if r.get("Employee ID")}
    if target_emp_id:
        emp_ids.add(target_emp_id)
    profiles = {
        p.user.username: p
        for p in UserProfile.objects.filter(user__username__in=emp_ids).select_related("department", "section")
    }

    # Filter by scope & section code
    filtered_records = []
    for r in attendance:
        from attendance.services.analytics_service import parse_date
        date_str = r.get("Date", "")
        date_obj = parse_date(date_str)
        if not date_obj:
            continue
        if not (start_date <= date_obj.date() <= end_date):
            continue

        emp_id = r.get("Employee ID")

        # Apply scope filters
        if not is_superuser and scope != "ALL":
            if scope == "OWN":
                if emp_id != request.user.username:
                    continue
            else:
                if expected_dtname4:
                    if r.get("Day") != expected_dtname4:
                        continue
                else:
                    if emp_id not in accessible_users:
                        continue

        # Filter by section code if provided (for superuser ONLY)
        if section_param and is_superuser:
            day_val = str(r.get("Day") or "").lower()
            if section_param == "s63":
                if not ("sector 63" in day_val or "s63" in day_val):
                    continue
            elif section_param == "c39":
                if not ("phase 2" in day_val or "c39" in day_val):
                    continue

        # Apply employee filter if requested and permitted
        if target_emp_id and emp_id != target_emp_id:
            continue

        filtered_records.append(r)

    # 5. Handle standard filters in Python
    final_records = []
    for record in filtered_records:
        date_str = record.get("Date", "")
        from attendance.services.analytics_service import parse_date
        date_obj = parse_date(date_str)

        in_time = record.get("In Time", "").strip()
        out_time = record.get("Out Time", "").strip()
        working_hours = safe_float(record.get("Working Hours"))
        late_minutes = safe_float(record.get("Late Minutes"))
        leave_type = record.get("Leave Type", "")
        attendance_status = record.get("Attendance Status", "")

        has_in = bool(in_time) and in_time not in ("00:00", "—", "")
        has_out = bool(out_time) and out_time not in ("00:00", "—", "")
        is_weekend = date_obj and date_obj.weekday() == 6 if date_obj else False
        is_holiday = (
            date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1
            if date_obj
            else False
        )
        is_today = date_obj and date_obj.date() == datetime.now().date()
        is_late = late_minutes > 0.0

        if is_holiday:
            if not has_in and not has_out:
                computed_status = "Holiday"
            else:
                computed_status = "Present"
        elif is_today and has_in and not is_late and not has_out:
            computed_status = "Present"
        elif (has_in and not has_out) or (has_out and not has_in):
            computed_status = "Mispunch"
        elif not has_in and not has_out:
            if is_weekend:
                computed_status = "Rest Day"
            else:
                computed_status = "Absent"
        else:
            if working_hours >= 8.0:
                computed_status = "Present"
            else:
                computed_status = "CL(0.5d)"

        if filter_type == "date":
            if len(filter_value) == 5:
                filter_value_parsed = f"{start_date.year}-{filter_value}"
            else:
                filter_value_parsed = filter_value
            try:
                target_date = datetime.strptime(filter_value_parsed, "%Y-%m-%d").date()
                if not date_obj or date_obj.date() != target_date:
                    continue
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid date value"}, status=400)

        elif filter_type == "attendance_status":
            if filter_value == "Present":
                if computed_status != "Present":
                    continue
            elif filter_value in ["Leaves", "Absent"]:
                if not (not has_in and (date_obj and date_obj.weekday() != 6)):
                    continue
            elif filter_value == "Rest Days":
                if not (not has_in and (date_obj and (date_obj.weekday() == 6 or (date_obj.year == 2026 and date_obj.month == 7 and date_obj.day == 1)))):
                    continue
            elif filter_value == "Mispunches":
                if computed_status != "Mispunch":
                    continue
            elif filter_value == "CL(0.5d)":
                if computed_status != "CL(0.5d)":
                    continue
            else:
                if attendance_status != filter_value:
                    continue

        elif filter_type == "late":
            if late_minutes <= 0:
                continue

        elif filter_type == "leave_type":
            if leave_type != filter_value:
                continue

        elif filter_type == "department" or filter_type == "section":
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
            if org_path != filter_value:
                continue

        final_records.append(record)

    # Sort final_records: ascending by employee_id, then descending by date
    final_records.sort(key=lambda r: r.get("Employee ID", ""))
    from attendance.services.analytics_service import parse_date
    final_records.sort(key=lambda r: parse_date(r.get("Date")) or date(1970, 1, 1), reverse=True)

    # Map to structured dictionary representation matching dashboard layout
    formatted_records = []
    for record in final_records:
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
        from attendance.services.analytics_service import parse_date
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
        # Calculate late minutes dynamically using the helper function
        late_minutes = 0.0
        if has_in and ":" in in_time:
            try:
                h, m = map(int, in_time.split(":"))
                wt_id = record.get("WT ID") or record.get("WTID")
                shift_raw = str(record.get("Shift") or "").strip()
                is_night_shift = "Night" in shift_raw
                shift_start = get_shift_start_minutes(wt_id, is_night_shift, in_time)
                if h * 60 + m > shift_start:
                    late_minutes = float((h * 60 + m) - shift_start)
            except Exception:
                pass
        if late_minutes == 0:
            try:
                late_minutes = float(record.get("Late Minutes") or 0.0)
            except Exception:
                late_minutes = 0.0

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

        formatted_records.append(
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
                "late_minutes": late_minutes,
                "wt_id": record.get("WT ID") or record.get("WTID"),
            }
        )

    return JsonResponse({
        "success": True,
        "filter_type": filter_type,
        "filter_value": filter_value,
        "count": len(formatted_records),
        "records": formatted_records
    })
