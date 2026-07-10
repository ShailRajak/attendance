from typing import Optional
from django.contrib.auth.models import User
from django.db.models import QuerySet


class RBACService:
    @staticmethod
    def has_permission(user: User, permission_code: str) -> bool:
        """
        Check if a user has a specific permission code.
        Superusers have all permissions.
        """
        from attendance.models import RolePermission

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
        from attendance.models import UserProfile

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
