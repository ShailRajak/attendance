from django.db.models import QuerySet
from django.contrib.auth.models import User
from attendance.models import UserProfile, Company, Plant, Department, Section, Team


class OrganizationService:
    @staticmethod
    def get_employees_in_team(team) -> QuerySet:
        return UserProfile.objects.filter(team=team, team__is_active=True).select_related(
            "user", "role", "company", "plant", "department", "section", "team"
        )

    @staticmethod
    def get_employees_in_section(section) -> QuerySet:
        return UserProfile.objects.filter(section=section, section__is_active=True).select_related(
            "user", "role", "company", "plant", "department", "section", "team"
        )

    @staticmethod
    def get_employees_in_department(department) -> QuerySet:
        return UserProfile.objects.filter(
            department=department, department__is_active=True
        ).select_related("user", "role", "company", "plant", "department", "section", "team")

    @staticmethod
    def get_employees_in_plant(plant) -> QuerySet:
        return UserProfile.objects.filter(plant=plant, plant__is_active=True).select_related(
            "user", "role", "company", "plant", "department", "section", "team"
        )

    @staticmethod
    def get_employees_in_company(company) -> QuerySet:
        return UserProfile.objects.filter(company=company, company__is_active=True).select_related(
            "user", "role", "company", "plant", "department", "section", "team"
        )

    @staticmethod
    def get_organization_path(profile: UserProfile) -> str:
        """
        Return organization path string, e.g., 'Company > Plant > Department > Section > Team'
        """
        if not profile:
            return ""
        parts = []
        if profile.company:
            parts.append(profile.company.name)
        if profile.plant:
            parts.append(profile.plant.name)
        if profile.department:
            parts.append(profile.department.name)
        if profile.section:
            parts.append(profile.section.name)
        if profile.team:
            parts.append(profile.team.name)
        return " > ".join(parts)

    @staticmethod
    def get_subordinates(user: User) -> QuerySet:
        """
        Returns the subordinates QuerySet for a given user.
        Subordinates are profiles that belong to the user's organization nodes
        at levels below the user's own assignment.
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

        # If they are a Team Leader (even if not explicitly assigned a team on profile)
        led_teams = Team.objects.filter(leader=user, is_active=True)
        if led_teams.exists():
            return (
                UserProfile.objects.filter(team__in=led_teams)
                .exclude(user=user)
                .select_related("user", "role", "company", "plant", "department", "section", "team")
            )

        # If they belong to a team (lowest level, no subordinates unless they are leader)
        if profile.team:
            return UserProfile.objects.none()

        # If they belong to a section (but no team)
        if profile.section:
            return (
                UserProfile.objects.filter(section=profile.section)
                .exclude(user=user)
                .select_related("user", "role", "company", "plant", "department", "section", "team")
            )

        # If they belong to a department
        if profile.department:
            return (
                UserProfile.objects.filter(department=profile.department)
                .exclude(user=user)
                .select_related("user", "role", "company", "plant", "department", "section", "team")
            )

        # If they belong to a plant
        if profile.plant:
            return (
                UserProfile.objects.filter(plant=profile.plant)
                .exclude(user=user)
                .select_related("user", "role", "company", "plant", "department", "section", "team")
            )

        # If they belong to a company
        if profile.company:
            return (
                UserProfile.objects.filter(company=profile.company)
                .exclude(user=user)
                .select_related("user", "role", "company", "plant", "department", "section", "team")
            )

        return UserProfile.objects.none()
