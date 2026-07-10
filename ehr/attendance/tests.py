from django.test import TestCase
from django.contrib.auth.models import User
from attendance.models import Role, Section, Permission, RolePermission, UserProfile
from attendance.services.rbac_service import RBACService


class RBACSystemTests(TestCase):
    def setUp(self):
        # 1. Fetch Permissions created by data migration
        self.perm_view_own = Permission.objects.get(code="attendance.view_own")
        self.perm_view_section = Permission.objects.get(code="attendance.view_section")
        self.perm_edit = Permission.objects.get(code="attendance.edit")

        # 2. Fetch Roles created by data migration
        self.role_employee = Role.objects.get(code="employee")
        self.role_supervisor = Role.objects.get(code="supervisor")
        self.role_admin = Role.objects.get(code="admin")

        # 3. Fetch Sections or create test-specific ones
        self.section_smt = Section.objects.get(code="s63_smt")
        self.section_assy = Section.objects.get(code="s63_assy")

        # 4. Create Users
        self.user_emp = User.objects.create_user(
            username="emp123", password="password"
        )
        self.profile_emp = UserProfile.objects.create(
            user=self.user_emp, role=self.role_employee, section=None
        )

        self.user_sup = User.objects.create_user(
            username="sup123", password="password"
        )
        self.profile_sup = UserProfile.objects.create(
            user=self.user_sup, role=self.role_supervisor, section=self.section_smt
        )

        self.user_admin = User.objects.create_user(
            username="admin123", password="password"
        )
        self.profile_admin = UserProfile.objects.create(
            user=self.user_admin, role=self.role_admin, section=None
        )

        self.user_superuser = User.objects.create_superuser(
            username="root", password="password"
        )

    def test_monkey_patch_has_permission(self):
        """
        Tests that user.has_permission is available and resolves properly.
        """
        self.assertTrue(self.user_emp.has_permission("attendance.view_own"))
        self.assertFalse(self.user_emp.has_permission("attendance.view_section"))
        self.assertFalse(self.user_emp.has_permission("attendance.edit"))

        self.assertTrue(self.user_sup.has_permission("attendance.view_own"))
        self.assertTrue(self.user_sup.has_permission("attendance.view_section"))
        self.assertFalse(self.user_sup.has_permission("attendance.edit"))

        self.assertTrue(self.user_superuser.has_permission("attendance.edit"))
        self.assertTrue(self.user_superuser.has_permission("any.random.perm"))

    def test_get_scope(self):
        """
        Tests resolving data scopes.
        """
        self.assertEqual(RBACService.get_scope(self.user_emp), "OWN")
        self.assertEqual(RBACService.get_scope(self.user_sup), "SECTION")
        self.assertEqual(RBACService.get_scope(self.user_admin), "ALL")
        self.assertEqual(RBACService.get_scope(self.user_superuser), "ALL")

    def test_get_accessible_employees(self):
        """
        Tests filtering employee profiles by scope.
        """
        # Employee sees only self
        emp_list = list(
            RBACService.get_accessible_employees(self.user_emp).values_list(
                "user__username", flat=True
            )
        )
        self.assertEqual(emp_list, ["emp123"])

        # Supervisor sees only SMT section profiles (which is just them for now)
        sup_list = list(
            RBACService.get_accessible_employees(self.user_sup).values_list(
                "user__username", flat=True
            )
        )
        self.assertEqual(sup_list, ["sup123"])

        # Admin/Superuser sees all
        all_list = RBACService.get_accessible_employees(self.user_admin)
        self.assertEqual(all_list.count(), UserProfile.objects.count())

    def test_get_expected_dtname4(self):
        """
        Tests resolving the dtname4 string for section filtering.
        """
        self.assertIsNone(RBACService.get_expected_dtname4(self.user_emp))
        self.assertEqual(
            RBACService.get_expected_dtname4(self.user_sup), "Sector 63 - SMT PD"
        )
        self.assertIsNone(RBACService.get_expected_dtname4(self.user_superuser))

    def test_organization_hierarchy_and_subordinates(self):
        """
        Tests the dynamic Company -> Plant -> Department -> Section -> Team hierarchy
        and get_subordinates functionality.
        """
        from attendance.models import Company, Plant, Department, Team
        from attendance.services.organization_service import OrganizationService

        # 1. Create company
        comp = Company.objects.create(name="Test Company", code="t_comp")
        
        # 2. Create plants
        plant_a = Plant.objects.create(company=comp, name="Plant A", code="p_a")

        # 3. Create department
        dept = Department.objects.create(plant=plant_a, name="Production", code="t_dept")

        # Update test sections
        self.section_smt.department = dept
        self.section_smt.save()

        # 4. Create team
        team_alpha = Team.objects.create(section=self.section_smt, name="Alpha", code="t_alpha", leader=self.user_sup)

        # Update profiles
        self.profile_emp.company = comp
        self.profile_emp.plant = plant_a
        self.profile_emp.department = dept
        self.profile_emp.section = self.section_smt
        self.profile_emp.team = team_alpha
        self.profile_emp.save()

        self.profile_sup.company = comp
        self.profile_sup.plant = plant_a
        self.profile_sup.department = dept
        self.profile_sup.section = self.section_smt
        self.profile_sup.save()

        # 5. Check path
        path = OrganizationService.get_organization_path(self.profile_emp)
        self.assertEqual(path, "Test Company > Plant A > Production > Sector 63 - SMT PD > Alpha")

        # 6. Check subordinates
        # Team leader (user_sup) gets members of team_alpha
        subs = list(OrganizationService.get_subordinates(self.user_sup).values_list("user__username", flat=True))
        self.assertEqual(subs, ["emp123"])

        # Employee (user_emp) has team, so gets no subordinates
        self.assertEqual(OrganizationService.get_subordinates(self.user_emp).count(), 0)
