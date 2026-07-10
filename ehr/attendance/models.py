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



class LeaveRequest(models.Model):
    CATEGORY_CHOICES = [
        ("casual", "Casual Leave"),
        ("sick", "Sick Leave"),
        ("earned", "Earned Leave"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaves")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="casual"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category} ({self.start_date} to {self.end_date}) - {self.status}"


class OvertimeRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="overtimes")
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.hours}h) - {self.status}"


class CorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="corrections")
    date = models.DateField()
    correct_in_time = models.CharField(max_length=5)  # format: "HH:MM"
    correct_out_time = models.CharField(max_length=5)  # format: "HH:MM"
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.correct_in_time} - {self.correct_out_time}) - {self.status}"


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


