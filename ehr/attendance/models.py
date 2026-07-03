from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('smt_pd', 'SMT PD'),
        ('assy_pd', 'ASSY PD'),
    ]
    SECTION_CHOICES = [
        ('s63', 'S63'),
        ('c39', 'C39'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    section = models.CharField(max_length=10, choices=SECTION_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.section or 'N/A'})"


class LeaveRequest(models.Model):
    CATEGORY_CHOICES = [
        ('casual', 'Casual Leave'),
        ('sick', 'Sick Leave'),
        ('earned', 'Earned Leave'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='casual')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category} ({self.start_date} to {self.end_date}) - {self.status}"


class OvertimeRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='overtimes')
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.hours}h) - {self.status}"


class CorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='corrections')
    date = models.DateField()
    correct_in_time = models.CharField(max_length=5)  # format: "HH:MM"
    correct_out_time = models.CharField(max_length=5)  # format: "HH:MM"
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.correct_in_time} - {self.correct_out_time}) - {self.status}"

