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
            messages.success(request, f"Logged in as {employee_id}!")
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
