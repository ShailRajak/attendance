from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from attendance.models import AttendanceRecord, LeaveRequest, OvertimeRequest, CorrectionRequest
from attendance.services.cache_service import invalidate_cache

@receiver([post_save, post_delete], sender=AttendanceRecord)
@receiver([post_save, post_delete], sender=LeaveRequest)
@receiver([post_save, post_delete], sender=OvertimeRequest)
@receiver([post_save, post_delete], sender=CorrectionRequest)
def handle_db_change(sender, instance, **kwargs):
    """
    Invalidate global metadata cache on any database modifications.
    """
    invalidate_cache()
