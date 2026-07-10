from django.db import transaction
from attendance.models import Permission, Role, RolePermission


class PermissionService:
    @staticmethod
    def get_all_permissions():
        """
        Get all system permissions ordered by module.
        """
        return Permission.objects.all().order_by("module", "name")

    @staticmethod
    def get_permissions_by_module() -> dict[str, list[Permission]]:
        """
        Group system permissions by their module.
        """
        permissions = Permission.objects.all().order_by("module", "name")
        grouped = {}
        for p in permissions:
            module_name = p.module.capitalize()
            grouped.setdefault(module_name, []).append(p)
        return grouped

    @staticmethod
    def get_role_permission_codes(role: Role) -> set[str]:
        """
        Get a set of permission codes assigned to a role.
        """
        return set(
            RolePermission.objects.filter(role=role).values_list(
                "permission__code", flat=True
            )
        )

    @staticmethod
    def update_role_permissions(role: Role, permission_ids: list[int]) -> None:
        """
        Sync a role's permissions by replacing all current mappings with the specified set.
        """
        with transaction.atomic():
            RolePermission.objects.filter(role=role).delete()
            for perm_id in permission_ids:
                try:
                    perm = Permission.objects.get(id=perm_id)
                    RolePermission.objects.create(role=role, permission=perm)
                except Permission.DoesNotExist:
                    continue
