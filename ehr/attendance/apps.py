from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    name = "attendance"

    def ready(self):
        from django.contrib.auth.models import User
        from attendance.services.rbac_service import RBACService

        def user_has_permission(self, permission_code: str) -> bool:
            return RBACService.has_permission(self, permission_code)

        User.add_to_class("has_permission", user_has_permission)

