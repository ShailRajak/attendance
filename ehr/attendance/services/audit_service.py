from django.contrib.auth.models import User
from attendance.models import AuditLog


class AuditService:
    @staticmethod
    def log(user, action_type: str, description: str, target_user: User = None) -> AuditLog:
        """
        Creates an audit entry for user actions and system changes.
        """
        return AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action_type=action_type,
            target_user=target_user,
            description=description,
        )
