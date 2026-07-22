# Reload trigger for Ultra-Modern Glassmorphic Control Bar UI upgrade
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
from attendance.services.attendance_service import get_attendance_api_data, get_home_dashboard_data
from attendance.services.analytics_service import get_overtime_dashboard_data, get_leaves_dashboard_data
from attendance.services.organization_service import get_pwa_manifest, get_pwa_service_worker


@login_required
def home(request):
    """
    Home Page - Secured with login_required and shows the EHR Portals (Dashboard, Leaves, OT, Corrections, Approvals)
    """
    # Purge any flash messages on home load to prevent duplicate alert banners
    storage = messages.get_messages(request)
    for m in list(storage):
        pass
    for s in getattr(storage, "storages", []):
        if hasattr(s, "_queued_messages"):
            s._queued_messages = []

    # Handle POST Submissions (Dashboard Filter)
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "filter_dashboard":
            query_employee_id = request.POST.get("employee_id", "").strip()
            start_date = request.POST.get("start_date") or request.POST.get("custom_start")
            end_date = request.POST.get("end_date") or request.POST.get("custom_end")
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
        get_params=request.GET,
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
        custom_start=request.GET.get("custom_start"),
        custom_end=request.GET.get("custom_end"),
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
    from attendance.services.auth_service import RBACService, resolve_user_role_and_section, get_expected_dtname4
    from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db
    from attendance.services.analytics_service import get_scope_overtime_summary

    # 1. Enforce RBAC bounds and resolve user scope
    accessible_users = set(
        RBACService.get_accessible_employees(request.user).values_list("user__username", flat=True)
    )
    scope = RBACService.get_scope(request.user)
    is_superuser = request.user.is_superuser
    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))
    role, section = resolve_user_role_and_section(request.user)

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
            start_date = start_dt.date()

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            from attendance.utils.date_helpers import get_attendance_date_range
            _, end_dt = get_attendance_date_range()
            end_date = end_dt.date()
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date format"}, status=400)

    # 4. Handle overtime_level filtering
    if filter_type == "overtime_level":
        ot_config = OvertimeLimitConfig.load()
        low_limit = ot_config.ot_low_limit
        medium_limit = ot_config.ot_medium_limit

        expected_dtname4 = get_expected_dtname4(role, section, request.user.username)
        is_all_scope = is_superuser or scope == "ALL"

        scope_summary = get_scope_overtime_summary(
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

    # 3. Base Fetching: Fetch raw records as dicts depending on role
    if role.lower() in ("own", "employee"):
        raw_records = fetch_attendance(target_emp_id, start_date_str, end_date_str)
    else:
        raw_records = fetch_attendance_from_db(target_emp_id, start_date_str, end_date_str)

    # Apply RBAC filtering on raw records
    if not is_superuser and scope != "ALL":
        if scope == "OWN":
            raw_records = [r for r in raw_records if r.get("Employee ID") == request.user.username]
        else:
            expected_dtname4 = get_expected_dtname4(role, section, request.user.username)
            if expected_dtname4:
                raw_records = [r for r in raw_records if r.get("Day") == expected_dtname4]
            else:
                raw_records = [r for r in raw_records if r.get("Employee ID") in accessible_users]

    # Filter by section code if provided (for admin/superuser ONLY)
    section_param = request.GET.get("section", "").strip()
    is_admin = is_superuser or role == "admin"
    if section_param and is_admin:
        if section_param == "s63":
            raw_records = [
                r for r in raw_records 
                if "sector 63" in (r.get("Day") or "").lower() or "s63" in (r.get("Day") or "").lower()
            ]
        elif section_param == "c39":
            raw_records = [
                r for r in raw_records 
                if "phase 2" in (r.get("Day") or "").lower() or "c39" in (r.get("Day") or "").lower()
            ]

    # Apply employee filter if requested
    if target_emp_id:
        raw_records = [r for r in raw_records if r.get("Employee ID") == target_emp_id]

    # Sort descending by date
    # Raw record date format: DD-MM-YYYY
    from attendance.services.analytics_service import parse_date
    def get_record_date(r):
        dt = parse_date(r.get("Date", ""))
        return dt.date() if dt else datetime.min.date()

    raw_records.sort(key=get_record_date, reverse=True)

    formatted_records = []
    for record in raw_records:
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
            date_val = date_obj.date()
        else:
            date_display = date_str
            day_name = "—"
            is_weekend = False
            date_val = None

        is_holiday = (
            date_val and date_val.year == 2026 and date_val.month == 7 and date_val.day == 1
        )
        is_today = date_val and date_val == datetime.now().date()

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
        from attendance.models import UserProfile
        try:
            p = UserProfile.objects.select_related("department", "section").get(user__username=emp_id)
            if p.section:
                org_path = p.section.name
            elif p.department:
                org_path = p.department.name
        except UserProfile.DoesNotExist:
            org_path = record.get("Day", "—")

        # Apply target filters here
        if filter_type == "date":
            try:
                target_date = datetime.strptime(filter_value, "%Y-%m-%d").date()
            except ValueError:
                target_date = None
            if date_val != target_date:
                continue

        elif filter_type == "attendance_status":
            if filter_value in ("Leaves", "Absent"):
                if status not in ("Leaves", "Absent"):
                    continue
            elif filter_value == "Rest Days":
                if status not in ("Rest Day", "Holiday"):
                    continue
            elif filter_value == "Mispunches":
                if status != "Mispunch":
                    continue
            else:
                if status != filter_value:
                    continue

        elif filter_type == "late":
            try:
                late_val = float(record.get("Late Minutes") or 0.0)
            except (ValueError, TypeError):
                late_val = 0.0
            if late_val <= 0:
                continue

        elif filter_type == "leave_type":
            if record.get("Leave Type") != filter_value:
                continue

        elif filter_type == "department":
            if org_path != filter_value:
                continue

        elif filter_type == "section":
            if org_path != filter_value:
                continue

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
                "Card Punch OT": record.get("Card Punch OT", "0.0"),
                "Requested OT": record.get("Requested OT", "0.0"),
                "Weekend OT": record.get("Weekend OT", "0.0"),
                "Holiday OT": record.get("Holiday OT", "0.0"),
                "Total OT All": record.get("Total OT All", "0.0"),
            }
        )

    return JsonResponse({
        "success": True,
        "filter_type": filter_type,
        "filter_value": filter_value,
        "count": len(formatted_records),
        "records": formatted_records
    })
