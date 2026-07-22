import os
import openpyxl
from typing import Optional, Tuple
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.contrib.auth.models import User
from attendance.models import UserProfile, Company, Plant, Department, Section, Team, Role
from attendance.services.auth_service import AuditService


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


class SectionService:
    @staticmethod
    def create_section(
        name: str,
        code: str,
        description: str,
        location: str,
        created_by: User,
    ) -> Tuple[Optional[Section], str]:
        """
        Creates a new section.
        """
        if Section.objects.filter(code=code).exists():
            return None, f"Section with code '{code}' already exists."

        try:
            sec = Section.objects.create(
                name=name,
                code=code,
                description=description,
                location=location,
                created_by=created_by,
            )
            return sec, "Section created successfully."
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_section(
        sec_id: int,
        name: str,
        description: str,
        location: str,
        is_active: bool,
    ) -> Tuple[bool, str]:
        """
        Updates an existing section.
        """
        try:
            sec = Section.objects.get(id=sec_id)
            sec.name = name
            sec.description = description
            sec.location = location
            sec.is_active = is_active
            sec.save()
            return True, "Section updated successfully."
        except Section.DoesNotExist:
            return False, "Section not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def deactivate_section(sec_id: int) -> Tuple[bool, str]:
        """
        Soft deletes (deactivates) a section.
        """
        try:
            sec = Section.objects.get(id=sec_id)
            sec.is_active = False
            sec.save()
            return True, "Section deactivated successfully."
        except Section.DoesNotExist:
            return False, "Section not found."
        except Exception as e:
            return False, str(e)


class ImportService:
    @staticmethod
    def import_from_excel(file_wrapper, user):
        """
        Parses an Excel sheet to import Company, Plant, Department, Section, Team, and Users.
        Expected columns:
        - A: Company Name
        - B: Company Code
        - C: Plant Name
        - D: Plant Code
        - E: Department Name
        - F: Department Code
        - G: Section Name
        - H: Section Code
        - I: Team Name
        - J: Team Code
        - K: Employee ID (Username)
        - L: Password
        - M: Role Code (e.g., employee, supervisor)

        Returns (success_count, error_messages)
        """
        errors = []
        success_count = 0

        try:
            wb = openpyxl.load_workbook(file_wrapper, data_only=True)
            sheet = wb.active
        except Exception as e:
            return 0, [f"Failed to open Excel workbook: {e}"]

        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        if not rows:
            return 0, ["The uploaded Excel sheet contains no data rows."]

        try:
            with transaction.atomic():
                for idx, row in enumerate(rows, start=2):
                    if len(row) < 13:
                        errors.append(
                            f"Row {idx}: Missing columns. Expected at least 13 columns."
                        )
                        continue

                    (
                        comp_name,
                        comp_code,
                        plant_name,
                        plant_code,
                        dept_name,
                        dept_code,
                        sec_name,
                        sec_code,
                        team_name,
                        team_code,
                        emp_id,
                        passwd,
                        role_code,
                    ) = row[:13]

                    # Strip strings
                    comp_name = str(comp_name).strip() if comp_name else ""
                    comp_code = str(comp_code).strip() if comp_code else ""
                    plant_name = str(plant_name).strip() if plant_name else ""
                    plant_code = str(plant_code).strip() if plant_code else ""
                    dept_name = str(dept_name).strip() if dept_name else ""
                    dept_code = str(dept_code).strip() if dept_code else ""
                    sec_name = str(sec_name).strip() if sec_name else ""
                    sec_code = str(sec_code).strip() if sec_code else ""
                    team_name = str(team_name).strip() if team_name else ""
                    team_code = str(team_code).strip() if team_code else ""
                    emp_id = str(emp_id).strip() if emp_id else ""
                    passwd = str(passwd).strip() if passwd else ""
                    role_code = str(role_code).strip() if role_code else ""

                    if (
                        not comp_code
                        or not plant_code
                        or not dept_code
                        or not emp_id
                        or not passwd
                        or not role_code
                    ):
                        errors.append(
                            f"Row {idx}: Company code, Plant code, Department code, Employee ID, Password, and Role Code are required."
                        )
                        continue

                    # Retrieve Role
                    try:
                        role_obj = Role.objects.get(code=role_code, is_active=True)
                    except Role.DoesNotExist:
                        errors.append(
                            f"Row {idx}: Role with code '{role_code}' does not exist or is inactive."
                        )
                        continue

                    # 1. Company
                    company, _ = Company.objects.get_or_create(
                        code=comp_code, defaults={"name": comp_name or comp_code.upper()}
                    )

                    # 2. Plant
                    plant, _ = Plant.objects.get_or_create(
                        code=plant_code,
                        defaults={"company": company, "name": plant_name or plant_code.upper()},
                    )

                    # 3. Department
                    dept, _ = Department.objects.get_or_create(
                        code=dept_code,
                        defaults={"plant": plant, "name": dept_name or dept_code.upper()},
                    )

                    # 4. Section
                    sec = None
                    if sec_code:
                        sec, _ = Section.objects.get_or_create(
                            code=sec_code,
                            defaults={"department": dept, "name": sec_name or sec_code.upper()},
                        )

                    # 5. Team
                    team = None
                    if team_code and sec:
                        team, _ = Team.objects.get_or_create(
                            code=team_code,
                            defaults={"section": sec, "name": team_name or team_code.upper()},
                        )

                    # 6. User and UserProfile
                    if User.objects.filter(username=emp_id).exists():
                        errors.append(
                            f"Row {idx}: User with Employee ID '{emp_id}' already exists."
                        )
                        continue

                    new_user = User.objects.create_user(username=emp_id, password=passwd)
                    UserProfile.objects.create(
                        user=new_user,
                        role=role_obj,
                        company=company,
                        plant=plant,
                        department=dept,
                        section=sec,
                        team=team,
                    )

                    AuditService.log(
                        user=user,
                        action_type="USER_CREATED",
                        description=f"Imported user {emp_id} under {company.name} > {plant.name} > {dept.name}",
                        target_user=new_user,
                    )

                    success_count += 1

                if errors:
                    # Rollback transaction by raising an exception
                    raise Exception("Validation failed.")

        except Exception as e:
            if not errors:
                errors.append(f"Database insertion failed: {e}")
            return 0, errors

        return success_count, []


def get_pwa_service_worker():
    """
    Reads sw.js from disk and returns content and content type.
    """
    path = os.path.join(
        settings.BASE_DIR, "static", "attendance", "sw.js"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content, "application/javascript"


def get_pwa_manifest():
    """
    Reads manifest.json from disk and returns content and content type.
    """
    path = os.path.join(
        settings.BASE_DIR, "static", "attendance", "manifest.json"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content, "application/json"
