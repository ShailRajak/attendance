from attendance.services.role_service import resolve_user_role_and_section, get_expected_dtname4
from attendance.services.rbac_service import RBACService
from attendance.services.attendance_service import fetch_attendance, fetch_attendance_from_db

def get_attendance_api_data(user, get_params):
    """
    Business logic for attendance API, enforcing RBAC and query bounds.
    Returns (success, result_dict, status_code).
    """
    employee_id = get_params.get("employee_id")
    start_date = get_params.get("start_date")
    end_date = get_params.get("end_date")

    is_superuser = user.is_superuser
    role, section = resolve_user_role_and_section(user)
    scope = RBACService.get_scope(user)

    is_supervisor = is_superuser or (scope in ("TEAM", "SECTION", "DEPARTMENT", "PLANT", "COMPANY", "ALL"))

    if scope == "OWN" and not is_superuser:
        employee_id = user.username

    if not start_date or not end_date:
        return False, {"success": False, "message": "Missing Parameters"}, 400

    # Fetch attendance raw data
    fetch_emp_id = employee_id if employee_id else ""
    if is_supervisor:
        attendance = fetch_attendance_from_db(
            employee_id=fetch_emp_id, start_date=start_date, end_date=end_date
        )
    else:
        attendance = fetch_attendance(
            employee_id=fetch_emp_id, start_date=start_date, end_date=end_date
        )

    # Filter data based on RBAC rules and resolved section names
    expected_dtname4 = get_expected_dtname4(role, section, user.username)

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

    return True, {"success": True, "count": len(attendance), "data": attendance}, 200
