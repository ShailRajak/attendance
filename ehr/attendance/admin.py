from django.contrib import admin

from .models import UserProfile, LeaveRequest, OvertimeRequest, CorrectionRequest, AttendanceAPIConfig, Role, Permission, RolePermission, OvertimeLimitConfig, Feedback


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


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "category",
        "start_date",
        "end_date",
        "status",
        "created_at",
    )
    list_filter = ("category", "status")
    search_fields = ("user__username", "reason")


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "hours", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "reason")


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "correct_in_time",
        "correct_out_time",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("user__username", "reason")


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
