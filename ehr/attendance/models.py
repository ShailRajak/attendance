from django.db import models
from django.contrib.auth.models import User


class Role(models.Model):
    SCOPE_CHOICES = [
        ("OWN", "Own Data Only"),
        ("TEAM", "Team Data Only"),
        ("SECTION", "Section Data Only"),
        ("DEPARTMENT", "Department Data Only"),
        ("PLANT", "Plant Data Only"),
        ("COMPANY", "Company Data Only"),
        ("ALL", "All Data"),
    ]
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    data_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="OWN")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Plant(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="plants")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Section(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="sections", null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_sections"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Permission(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, unique=True)
    module = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"[{self.module}] {self.name} ({self.code})"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="permission_roles"
    )

    class Meta:
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class Team(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_teams")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="profiles"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="profiles", null=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="profiles", null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="profiles", null=True, blank=True)
    section = models.ForeignKey(
        Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="profiles"
    )
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="profiles")

    def __str__(self):
        role_name = self.role.name if self.role else "N/A"
        company_name = self.company.name if self.company else "N/A"
        return f"{self.user.username} - {role_name} ({company_name})"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="performed_audit_logs")
    action_type = models.CharField(max_length=100)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="target_audit_logs")
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} by {self.user.username if self.user else 'System'} - {self.timestamp}"






class AttendanceAPIConfig(models.Model):
    api_url = models.CharField(
        max_length=255,
        default="http://10.61.248.6",
        help_text="Base URL without port, e.g., http://10.61.248.6"
    )
    port = models.IntegerField(
        default=18010,
        help_text="Port number, e.g., 18010"
    )

    class Meta:
        verbose_name = "Attendance API Configuration"
        verbose_name_plural = "Attendance API Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"{self.api_url}:{self.port}"



class OvertimeLimitConfig(models.Model):
    ot_low_limit = models.FloatField(
        default=52.0,
        help_text="Overtime hours below this limit are classified as 'Low'"
    )
    ot_medium_limit = models.FloatField(
        default=78.0,
        help_text="Overtime hours below this limit (and above low limit) are classified as 'Medium'. Above this are 'High'."
    )

    class Meta:
        verbose_name = "Overtime Limit Configuration"
        verbose_name_plural = "Overtime Limit Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"OT Low Limit: {self.ot_low_limit}h | OT Medium Limit: {self.ot_medium_limit}h"


class Feedback(models.Model):
    PLANT_CHOICES = [
        ("S63", "Sector 63 (S63)"),
        ("C39", "Phase 2 (C39)"),
    ]

    employee_id = models.CharField(max_length=50, verbose_name="Employee ID")
    plant = models.CharField(max_length=10, choices=PLANT_CHOICES, verbose_name="Plant")
    feedback = models.TextField(verbose_name="Feedback")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"
        ordering = ["-date"]

    def __str__(self):
        return f"Feedback from {self.employee_id} ({self.plant}) on {self.date.strftime('%Y-%m-%d %H:%M')}"


class AttendanceRecord(models.Model):
    employee_id = models.CharField(max_length=50, db_index=True)
    employee_name = models.CharField(max_length=150, blank=True, default="")
    attendance_date = models.DateField(db_index=True)

    in_time = models.CharField(max_length=10, blank=True, default="")
    out_time = models.CharField(max_length=10, blank=True, default="")
    working_hours = models.FloatField(default=0.0, null=True, blank=True)
    work_time = models.FloatField(default=0.0, null=True, blank=True)

    card_punch_ot = models.FloatField(default=0.0, null=True, blank=True)
    requested_ot = models.FloatField(default=0.0, null=True, blank=True)
    weekend_ot = models.FloatField(default=0.0, null=True, blank=True)
    holiday_ot = models.FloatField(default=0.0, null=True, blank=True)
    ot4 = models.FloatField(default=0.0, null=True, blank=True)
    total_ot_all = models.FloatField(default=0.0, null=True, blank=True)
    req_overtime = models.FloatField(default=0.0, null=True, blank=True)
    approved_ot = models.FloatField(default=0.0, null=True, blank=True)

    wt_id = models.CharField(max_length=50, blank=True, default="")
    wt_type_no = models.CharField(max_length=50, blank=True, default="")
    attendance_source = models.CharField(max_length=100, blank=True, default="")
    day = models.CharField(max_length=100, blank=True, default="", db_index=True)  # Section name from dtName4
    attendance_status = models.CharField(max_length=100, blank=True, default="")
    shift = models.CharField(max_length=100, blank=True, default="")
    mobile = models.CharField(max_length=50, blank=True, default="")
    late_minutes = models.FloatField(default=0.0, null=True, blank=True)
    leave_type = models.CharField(max_length=100, blank=True, default="")
    workday = models.CharField(max_length=50, blank=True, default="")
    weekday = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("employee_id", "attendance_date")
        ordering = ["-attendance_date", "employee_id"]

    def __str__(self):
        return f"{self.employee_id} - {self.attendance_date} - {self.attendance_status}"

    def to_dict(self):
        """
        Convert to the dictionary structure matching the raw/formatter output format
        to maintain total backward compatibility with dashboard/analytics services.
        """
        def format_float(val):
            if val is None:
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)

        return {
            "Date": self.attendance_date.strftime("%d-%m-%Y") if self.attendance_date else "",
            "Employee ID": self.employee_id,
            "Employee Name": self.employee_name,
            "In Time": self.in_time,
            "Out Time": self.out_time,
            "Working Hours": format_float(self.working_hours),
            "Work Time": format_float(self.work_time),
            "Card Punch OT": format_float(self.card_punch_ot),
            "Requested OT": format_float(self.requested_ot),
            "Weekend OT": format_float(self.weekend_ot),
            "Holiday OT": format_float(self.holiday_ot),
            "OT4": format_float(self.ot4),
            "Total OT All": format_float(self.total_ot_all),
            "Req OverTime": format_float(self.req_overtime),
            "Approved OT": format_float(self.approved_ot),
            "WT ID": self.wt_id,
            "WT Type No": self.wt_type_no,
            "Attendance Source": self.attendance_source,
            "Day": self.day,
            "Attendance Status": self.attendance_status,
            "Shift": self.shift,
            "Mobile": self.mobile,
            "Late Minutes": format_float(self.late_minutes),
            "Leave Type": self.leave_type,
            "WorkDay": self.workday,
            "Weekday": self.weekday,
        }


class SyncLog(models.Model):
    sync_date = models.DateField(unique=True)
    status = models.CharField(
        max_length=20,
        choices=[("SUCCESS", "Success"), ("FAILED", "Failed")]
    )
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_unchanged = models.IntegerField(default=0)
    last_sync = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-sync_date"]

    def __str__(self):
        return f"{self.sync_date} - {self.status}"



