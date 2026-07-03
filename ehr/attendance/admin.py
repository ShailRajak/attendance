from django.contrib import admin
# pyrefly: ignore [missing-import]
from .models import UserProfile, LeaveRequest, OvertimeRequest, CorrectionRequest

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'section')
    list_filter = ('role', 'section')
    search_fields = ('user__username',)

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('user__username', 'reason')

@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'hours', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'reason')

@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'correct_in_time', 'correct_out_time', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'reason')

