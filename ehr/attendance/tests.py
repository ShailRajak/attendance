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


from datetime import date, timedelta
from unittest.mock import patch
from django.core.management import call_command
from attendance.models import AttendanceRecord, SyncLog
from attendance.management.commands.sync_attendance import get_cycle_dates, get_retention_cutoff


class AttendanceSyncTests(TestCase):
    def test_get_cycle_dates_10_july(self):
        # 10 July 2026
        # Previous fixed cycle: 21 May 2026 -> 20 June 2026
        # Current active cycle: 21 June 2026 -> 10 July 2026
        today = date(2026, 7, 10)
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        self.assertEqual(prev_start, date(2026, 5, 21))
        self.assertEqual(prev_end, date(2026, 6, 20))
        self.assertEqual(curr_start, date(2026, 6, 21))
        self.assertEqual(curr_end, date(2026, 7, 10))

    def test_get_cycle_dates_20_july(self):
        # 20 July 2026
        # Previous fixed cycle: 21 May 2026 -> 20 June 2026
        # Current active cycle: 21 June 2026 -> 20 July 2026
        today = date(2026, 7, 20)
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        self.assertEqual(prev_start, date(2026, 5, 21))
        self.assertEqual(prev_end, date(2026, 6, 20))
        self.assertEqual(curr_start, date(2026, 6, 21))
        self.assertEqual(curr_end, date(2026, 7, 20))

    def test_get_cycle_dates_21_july(self):
        # 21 July 2026
        # Previous fixed cycle: 21 June 2026 -> 20 July 2026
        # Current active cycle: 21 July 2026 -> 21 July 2026
        today = date(2026, 7, 21)
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        self.assertEqual(prev_start, date(2026, 6, 21))
        self.assertEqual(prev_end, date(2026, 7, 20))
        self.assertEqual(curr_start, date(2026, 7, 21))
        self.assertEqual(curr_end, date(2026, 7, 21))

    def test_get_cycle_dates_1_august(self):
        # 1 August 2026
        # Previous fixed cycle: 21 June 2026 -> 20 July 2026
        # Current active cycle: 21 July 2026 -> 1 August 2026
        today = date(2026, 8, 1)
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        self.assertEqual(prev_start, date(2026, 6, 21))
        self.assertEqual(prev_end, date(2026, 7, 20))
        self.assertEqual(curr_start, date(2026, 7, 21))
        self.assertEqual(curr_end, date(2026, 8, 1))

    def test_december_january_boundary(self):
        # Test Year Boundary (5 January 2027)
        # Previous fixed cycle: 21 November 2026 -> 20 December 2026
        # Current active cycle: 21 December 2026 -> 5 January 2027
        today = date(2027, 1, 5)
        (prev_start, prev_end), (curr_start, curr_end) = get_cycle_dates(today)
        self.assertEqual(prev_start, date(2026, 11, 21))
        self.assertEqual(prev_end, date(2026, 12, 20))
        self.assertEqual(curr_start, date(2026, 12, 21))
        self.assertEqual(curr_end, date(2027, 1, 5))

    def test_retention_cutoff(self):
        # 31 July 2026 -> cutoff starts 21 May 2026 (June cycle starts 21 May, kept)
        self.assertEqual(get_retention_cutoff(date(2026, 7, 31)), date(2026, 5, 21))
        # 1 August 2026 -> cutoff starts 21 June 2026 (June cycle starts 21 May, deleted)
        self.assertEqual(get_retention_cutoff(date(2026, 8, 1)), date(2026, 6, 21))

    @patch("attendance.management.commands.sync_attendance.fetch_single_date_with_status")
    def test_sync_db_write_modes_and_safety(self, mock_fetch):
        # Pre-seed some SyncLogs to simulate partial sync of previous cycle
        # We'll mark all days of previous cycle as SUCCESS except for 2026-06-15.
        d = date(2026, 5, 21)
        while d <= date(2026, 6, 20):
            if d != date(2026, 6, 15):
                SyncLog.objects.create(sync_date=d, status="SUCCESS")
            d += timedelta(days=1)

        # Pre-seed one AttendanceRecord on 2026-06-25 with old info (will check UPDATE)
        AttendanceRecord.objects.create(
            employee_id="KQ062001",
            employee_name="Old Name",
            attendance_date=date(2026, 6, 25),
            in_time="09:00",
            out_time="18:00",
            working_hours=8.0,
            day="Sector 63 - SMT PD",
            attendance_status="Present"
        )

        # Pre-seed one AttendanceRecord on 2026-06-26 with identical info (will check SKIP)
        AttendanceRecord.objects.create(
            employee_id="KQ062001",
            employee_name="Identical Name",
            attendance_date=date(2026, 6, 26),
            in_time="09:00",
            out_time="18:00",
            working_hours=8.0,
            day="Sector 63 - SMT PD",
            attendance_status="Present"
        )

        # Define API responses for fetch_single_date_with_status
        def mock_fetch_side_effect(dt):
            # KQ062001 on June 15 (unsynced prev): New INSERT
            if dt == date(2026, 6, 15):
                return True, [{
                    "EmpNo": "KQ062001",
                    "EmpName": "John Doe",
                    "YYMMDD": "20260615",
                    "GO1": "09:00",
                    "OUT1": "18:00",
                    "WorkTime1": "8.0",
                    "dtName4": "Sector 63 - SMT PD",
                    "WorkTypeName": "Present"
                }]
            # KQ062001 on June 25: changed employee_name to "New Name" (UPDATE check)
            elif dt == date(2026, 6, 25):
                return True, [{
                    "EmpNo": "KQ062001",
                    "EmpName": "New Name",
                    "YYMMDD": "20260625",
                    "GO1": "09:00",
                    "OUT1": "18:00",
                    "WorkTime1": "8.0",
                    "dtName4": "Sector 63 - SMT PD",
                    "WorkTypeName": "Present"
                }]
            # KQ062001 on June 26: identical (SKIP check)
            elif dt == date(2026, 6, 26):
                return True, [{
                    "EmpNo": "KQ062001",
                    "EmpName": "Identical Name",
                    "YYMMDD": "20260626",
                    "GO1": "09:00",
                    "OUT1": "18:00",
                    "WorkTime1": "8.0",
                    "dtName4": "Sector 63 - SMT PD",
                    "WorkTypeName": "Present"
                }]
            # Let 2026-07-08 fail completely (API Failure safety check)
            elif dt == date(2026, 7, 8):
                return False, []

            return True, []

        mock_fetch.side_effect = mock_fetch_side_effect

        # Run command for 11 July 2026 (target date is passed to date option)
        call_command("sync_attendance", date="2026-07-11")

        # 1. Verify INSERT
        rec_insert = AttendanceRecord.objects.get(attendance_date=date(2026, 6, 15), employee_id="KQ062001")
        self.assertEqual(rec_insert.employee_name, "John Doe")

        # 2. Verify UPDATE
        rec_update = AttendanceRecord.objects.get(attendance_date=date(2026, 6, 25), employee_id="KQ062001")
        self.assertEqual(rec_update.employee_name, "New Name")

        # 3. Verify API Failure: date 2026-07-08 SyncLog status is FAILED
        log_failed = SyncLog.objects.get(sync_date=date(2026, 7, 8))
        self.assertEqual(log_failed.status, "FAILED")

        # 4. Verify that other dates remain safe
        self.assertEqual(AttendanceRecord.objects.filter(attendance_date=date(2026, 6, 25)).count(), 1)

    @patch("attendance.management.commands.sync_attendance.fetch_single_date_with_status")
    def test_retention_deletion_execution(self, mock_fetch):
        mock_fetch.return_value = (True, [])

        # Seed record belonging to June cycle (21 May -> 20 June)
        AttendanceRecord.objects.create(
            employee_id="KQ062001",
            employee_name="June Emp",
            attendance_date=date(2026, 6, 19),
            in_time="09:00",
            out_time="18:00"
        )
        SyncLog.objects.create(sync_date=date(2026, 6, 19), status="SUCCESS")

        # Seed record belonging to July cycle (starts 21 June)
        AttendanceRecord.objects.create(
            employee_id="KQ062001",
            employee_name="July Emp",
            attendance_date=date(2026, 6, 22),
            in_time="09:00",
            out_time="18:00"
        )
        SyncLog.objects.create(sync_date=date(2026, 6, 22), status="SUCCESS")

        # Run command with date 1st August 2026
        call_command("sync_attendance", date="2026-08-01")

        # Verify June records are deleted
        self.assertFalse(AttendanceRecord.objects.filter(attendance_date=date(2026, 6, 19)).exists())
        self.assertFalse(SyncLog.objects.filter(sync_date=date(2026, 6, 19)).exists())

        # Verify July records are preserved
        self.assertTrue(AttendanceRecord.objects.filter(attendance_date=date(2026, 6, 22)).exists())
        self.assertTrue(SyncLog.objects.filter(sync_date=date(2026, 6, 22)).exists())
