import openpyxl
from django.db import transaction
from django.contrib.auth.models import User
from attendance.models import Company, Plant, Department, Section, Team, UserProfile, Role
from attendance.services.audit_service import AuditService


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
