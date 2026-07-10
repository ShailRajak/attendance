from typing import Optional, Tuple
from django.contrib.auth.models import User
from django.db import transaction
from attendance.models import Role, Section, UserProfile


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
        # Fallback username checks
        if username == "19105540":
            return "Phase 2 - Marketing"
        elif username == "19105639":
            return "Sector 63 - Marketing"
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
