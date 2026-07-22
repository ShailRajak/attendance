from django.contrib import admin

# pyrefly: ignore [missing-import]
from .models import (
    UserProfile,
    AttendanceAPIConfig, Role, Permission, RolePermission,
    OvertimeLimitConfig, Feedback, AttendanceRecord, SyncLog
)


@admin.register(AttendanceAPIConfig)
class AttendanceAPIConfigAdmin(admin.ModelAdmin):
    list_display = ("api_url", "port")

    def has_add_permission(self, request):
        # Allow adding if there are no configurations yet
        return self.model.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        # Do not allow deleting the configuration to prevent system malfunction
        return False


@admin.register(OvertimeLimitConfig)
class OvertimeLimitConfigAdmin(admin.ModelAdmin):
    list_display = ("ot_low_limit", "ot_medium_limit")

    def has_add_permission(self, request):
        return self.model.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "section")
    list_filter = ("role", "section")
    search_fields = ("user__username",)




@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "data_scope", "is_active")
    list_filter = ("data_scope", "is_active")
    search_fields = ("name", "code")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "module")
    list_filter = ("module",)
    search_fields = ("name", "code")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "plant", "feedback", "date")
    list_filter = ("plant", "date")
    search_fields = ("employee_id", "feedback")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "employee_name",
        "attendance_date",
        "in_time",
        "out_time",
        "working_hours",
        "attendance_status",
        "day",
    )
    list_filter = ("attendance_date", "day", "attendance_status", "shift")
    search_fields = ("employee_id", "employee_name", "day")
    date_hierarchy = "attendance_date"


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "sync_date",
        "status",
        "records_created",
        "records_updated",
        "records_unchanged",
        "last_sync",
    )
    list_filter = ("status", "sync_date")
    date_hierarchy = "sync_date"

