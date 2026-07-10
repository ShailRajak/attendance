from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from attendance.models import UserProfile

def validate_signup(employee_id, password, confirm_password, role, company, plant, department, section, team):
    """
    Validates user signup parameters.
    Returns (is_valid, error_message).
    """
    from attendance.models import Role

    if not employee_id or not password:
        return False, "Employee ID and password are required."
    
    if password != confirm_password:
        return False, "Passwords do not match."
        
    try:
        role_obj = Role.objects.get(code=role, is_active=True)
    except Role.DoesNotExist:
        return False, "Selected role does not exist."

    if not company:
        return False, "Company assignment is required."
    
    if not plant:
        return False, "Plant assignment is required."

    if role_obj.data_scope == "SECTION" and not section:
        return False, f"Section is required for role '{role_obj.name}'."

    if role_obj.data_scope == "TEAM" and not team:
        return False, f"Team is required for role '{role_obj.name}'."
        
    if User.objects.filter(username=employee_id).exists():
        return False, "An account with this Employee ID already exists."
        
    return True, None

def register_user(employee_id, password, role, company, plant, department, section, team):
    """
    Registers a new user and creates their UserProfile within a transaction.
    Returns (user, error_message).
    """
    from attendance.models import Role, Company, Plant, Department, Section, Team, UserProfile

    try:
        with transaction.atomic():
            user = User.objects.create_user(username=employee_id, password=password)
            role_obj = Role.objects.get(code=role, is_active=True)
            
            comp_obj = Company.objects.get(code=company, is_active=True) if company else None
            plant_obj = Plant.objects.get(code=plant, is_active=True) if plant else None
            dept_obj = Department.objects.get(code=department, is_active=True) if department else None
            sec_obj = Section.objects.get(code=section, is_active=True) if section else None
            team_obj = Team.objects.get(code=team, is_active=True) if team else None

            # Auto-resolve parent nodes if child node was selected
            if team_obj and not sec_obj:
                sec_obj = team_obj.section
            if sec_obj and not dept_obj:
                dept_obj = sec_obj.department

            UserProfile.objects.create(
                user=user,
                role=role_obj,
                company=comp_obj,
                plant=plant_obj,
                department=dept_obj,
                section=sec_obj,
                team=team_obj,
            )
            return user, None
    except Exception as e:
        return None, str(e)

def authenticate_user(request, employee_id, password):
    """
    Authenticates a user using credentials.
    Returns (user, error_message).
    """
    if not employee_id or not password:
        return None, "Employee ID and password are required."
        
    user = authenticate(request, username=employee_id, password=password)
    if user is not None:
        return user, None
    return None, "Invalid Employee ID or Password."

def login_user(request, user):
    """
    Logs in the authenticated user.
    """
    login(request, user)

def logout_user(request):
    """
    Logs out the authenticated user.
    """
    logout(request)
