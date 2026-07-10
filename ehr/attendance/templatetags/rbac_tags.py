from django import template
from attendance.services.rbac_service import RBACService

register = template.Library()


@register.filter(name="has_permission")
def has_permission(user, perm_code: str) -> bool:
    """
    Checks if a user has a specific permission code in Django templates.
    Usage: {% if user|has_permission:"role.manage" %}
    """
    if not user or not user.is_authenticated:
        return False
    return RBACService.has_permission(user, perm_code)
