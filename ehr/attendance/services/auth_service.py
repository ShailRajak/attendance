from typing import Optional, Tuple
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from attendance.models import UserProfile, Role, Section, Permission, RolePermission, AuditLog


def validate_signup(employee_id, password, confirm_password, role, company, plant, department, section, team):
    """
    Validates user signup parameters.
    Returns (is_valid, error_message).
    """
    from attendance.models import Role, Section, User
    from django.db.models import Q

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

    if role_obj.code == "management":
        if not section:
            return False, "Department is required for Management role."
        sec_exists = Section.objects.filter(is_active=True).filter(
            Q(code=section) | Q(id=int(section) if str(section).isdigit() else -1)
        ).exists()
        if not sec_exists:
            return False, "Selected department does not exist."

    if User.objects.filter(username=employee_id).exists():
        return False, "An account with this Employee ID already exists."
        
    return True, None


def register_user(employee_id, password, role, company, plant, department, section, team):
    """
    Registers a new user and creates their UserProfile within a transaction.
    Returns (user, error_message).
    """
    from attendance.models import Company, Plant, Department, Section, Team

    try:
        with transaction.atomic():
            user = User.objects.create_user(username=employee_id, password=password)
            role_obj = Role.objects.get(code=role, is_active=True)
            
            comp_obj = Company.objects.filter(code=company, is_active=True).first() if company else None
            plant_obj = Plant.objects.filter(code=plant, is_active=True).first() if plant else None
            if not plant_obj and plant:
                plant_obj = Plant.objects.filter(id=int(plant) if str(plant).isdigit() else -1, is_active=True).first()

            sec_obj = None
            dept_obj = None
            if role_obj.code == "management" and section:
                sec_obj = Section.objects.filter(code=section, is_active=True).first()
                if not sec_obj and str(section).isdigit():
                    sec_obj = Section.objects.filter(id=int(section), is_active=True).first()
                if sec_obj and sec_obj.department:
                    dept_obj = sec_obj.department

            UserProfile.objects.create(
                user=user,
                role=role_obj,
                company=comp_obj,
                plant=plant_obj,
                department=dept_obj,
                section=sec_obj,
                team=None,
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


def resolve_user_role_and_section(user: User) -> Tuple[str, Optional[str]]:
    """
    Resolves the role and section codes of a user dynamically from the database.
    Superusers default to ('admin', None).
    """
    if not user or not user.is_authenticated:
        return "employee", None

    if user.is_superuser:
        return "admin", None

    if hasattr(user, "profile"):
        role_code = user.profile.role.code if user.profile.role else "employee"
        section_code = (
            user.profile.section.code if user.profile.section else None
        )
        return role_code, section_code

    return "employee", None


def get_expected_dtname4(
    role: str, section: Optional[str], username: Optional[str] = None
) -> Optional[str]:
    """
    Resolves the expected dtName4 (Day column in attendance records)
    corresponding to a section. Preserves backward compatibility.
    """
    if not section:
        # Fallback username checks (safety net - these users now have proper section records)
        if username == "19105540":
            return "Phase 2 - Marketing"
        elif username == "19105639":
            return "Sector 63 - Marketing"
        elif username == "19105619":
            return "Sector 63 - Purchase"
        return None

    # Try resolving from the Section model name
    try:
        sec_obj = Section.objects.get(code=section)
        return sec_obj.name
    except Section.DoesNotExist:
        # Fallback to old hardcoded names
        if role == "smt_pd":
            if section == "s63":
                return "Sector 63 - SMT PD"
            elif section == "c39":
                return "Phase 2 - SMT PD"
        elif role == "assy_pd":
            if section == "s63":
                return "Sector 63 - ASSY PD"
            elif section == "c39":
                return "Phase 2 - ASSY PD"
        return None


class RoleService:
    @staticmethod
    def create_role(
        name: str, code: str, description: str, data_scope: str, created_by: User
    ) -> Tuple[Optional[Role], str]:
        """
        Creates a new role in the database.
        """
        if Role.objects.filter(code=code).exists():
            return None, f"Role with code '{code}' already exists."

        try:
            role = Role.objects.create(
                name=name,
                code=code,
                description=description,
                data_scope=data_scope,
                created_by=created_by,
            )
            return role, "Role created successfully."
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_role(
        role_id: int, name: str, description: str, data_scope: str, is_active: bool
    ) -> Tuple[bool, str]:
        """
        Updates an existing role.
        """
        try:
            role = Role.objects.get(id=role_id)
            role.name = name
            role.description = description
            role.data_scope = data_scope
            role.is_active = is_active
            role.save()
            return True, "Role updated successfully."
        except Role.DoesNotExist:
            return False, "Role not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def deactivate_role(role_id: int) -> Tuple[bool, str]:
        """
        Soft deletes (deactivates) a role.
        """
        try:
            role = Role.objects.get(id=role_id)
            if role.code == "admin":
                return False, "The Admin role cannot be deactivated."
            role.is_active = False
            role.save()
            return True, "Role deactivated successfully."
        except Role.DoesNotExist:
            return False, "Role not found."
        except Exception as e:
            return False, str(e)


class RBACService:
    @staticmethod
    def has_permission(user: User, permission_code: str) -> bool:
        """
        Check if a user has a specific permission code.
        Superusers have all permissions.
        """
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if not hasattr(user, "profile") or not user.profile.role:
            return False

        # Inactive roles do not grant permissions
        if not user.profile.role.is_active:
            return False

        return RolePermission.objects.filter(
            role=user.profile.role, permission__code=permission_code
        ).exists()

    @staticmethod
    def get_scope(user: User) -> str:
        """
        Resolve the user's data scope: 'OWN', 'SECTION', or 'ALL'.
        """
        if not user or not user.is_authenticated:
            return "OWN"

        if user.is_superuser:
            return "ALL"

        if (
            not hasattr(user, "profile")
            or not user.profile.role
            or not user.profile.role.is_active
        ):
            return "OWN"

        return user.profile.role.data_scope

    @staticmethod
    def get_accessible_employees(user: User) -> QuerySet:
        """
        Get the list of UserProfiles accessible to the logged-in user.
        """
        if not user or not user.is_authenticated:
            return UserProfile.objects.none()

        if user.is_superuser:
            return UserProfile.objects.all().select_related(
                "user", "role", "company", "plant", "department", "section", "team"
            )

        if not hasattr(user, "profile"):
            return UserProfile.objects.none()

        profile = user.profile
        scope = RBACService.get_scope(user)
        base_qs = UserProfile.objects.all().select_related(
            "user", "role", "company", "plant", "department", "section", "team"
        )

        if scope == "OWN":
            return base_qs.filter(user=user)

        elif scope == "TEAM":
            if profile.team:
                return base_qs.filter(team=profile.team, team__is_active=True)
            return base_qs.filter(user=user)

        elif scope == "SECTION":
            if profile.section:
                return base_qs.filter(section=profile.section, section__is_active=True)
            return base_qs.filter(user=user)

        elif scope == "DEPARTMENT":
            if profile.department:
                return base_qs.filter(department=profile.department, department__is_active=True)
            return base_qs.filter(user=user)

        elif scope == "PLANT":
            if profile.plant:
                return base_qs.filter(plant=profile.plant, plant__is_active=True)
            return base_qs.filter(user=user)

        elif scope == "COMPANY":
            if profile.company:
                return base_qs.filter(company=profile.company, company__is_active=True)
            return base_qs.filter(user=user)

        elif scope == "ALL":
            return base_qs

        return base_qs.filter(user=user)

    @staticmethod
    def get_expected_dtname4(user: User) -> Optional[str]:
        """
        Get the expected department name for the user's assigned section if they have one.
        """
        if not user or not user.is_authenticated or user.is_superuser:
            return None
        if hasattr(user, "profile") and user.profile.section:
            return user.profile.section.name
        return None


class PermissionService:
    @staticmethod
    def get_all_permissions():
        """
        Get all system permissions ordered by module.
        """
        return Permission.objects.all().order_by("module", "name")

    @staticmethod
    def get_permissions_by_module() -> dict[str, list[Permission]]:
        """
        Group system permissions by their module.
        """
        permissions = Permission.objects.all().order_by("module", "name")
        grouped = {}
        for p in permissions:
            module_name = p.module.capitalize()
            grouped.setdefault(module_name, []).append(p)
        return grouped

    @staticmethod
    def get_role_permission_codes(role: Role) -> set[str]:
        """
        Get a set of permission codes assigned to a role.
        """
        return set(
            RolePermission.objects.filter(role=role).values_list(
                "permission__code", flat=True
            )
        )

    @staticmethod
    def update_role_permissions(role: Role, permission_ids: list[int]) -> None:
        """
        Sync a role's permissions by replacing all current mappings with the specified set.
        """
        with transaction.atomic():
            RolePermission.objects.filter(role=role).delete()
            for perm_id in permission_ids:
                try:
                    perm = Permission.objects.get(id=perm_id)
                    RolePermission.objects.create(role=role, permission=perm)
                except Permission.DoesNotExist:
                    continue


class UserService:
    @staticmethod
    def update_user_profile(
        user_id: int, role_code: str, section_code: str, is_active: bool
    ) -> tuple[bool, str]:
        """
        Update user profile role, section and active status in a transaction.
        """
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                user.is_active = is_active
                user.save()

                profile, _ = UserProfile.objects.get_or_create(user=user)

                # Fetch Role
                role = Role.objects.get(code=role_code)
                profile.role = role

                # Fetch Section (optional)
                if section_code:
                    section = Section.objects.get(code=section_code)
                    profile.section = section
                else:
                    profile.section = None

                profile.save()
                return True, "User profile updated successfully."
        except User.DoesNotExist:
            return False, "User not found."
        except Role.DoesNotExist:
            return False, f"Role with code '{role_code}' not found."
        except Section.DoesNotExist:
            return False, f"Section with code '{section_code}' not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def reset_password(user_id: int, new_password: str) -> tuple[bool, str]:
        """
        Set a new password for the specified user.
        """
        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            return True, "Password reset successfully."
        except User.DoesNotExist:
            return False, "User not found."
        except Exception as e:
            return False, str(e)


class AuditService:
    @staticmethod
    def log(user, action_type: str, description: str, target_user: User = None) -> AuditLog:
        """
        Creates an audit entry for user actions and system changes.
        """
        return AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action_type=action_type,
            target_user=target_user,
            description=description,
        )
