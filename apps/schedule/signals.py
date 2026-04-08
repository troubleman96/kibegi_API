import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import ScheduleService

logger = logging.getLogger("kibegi")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_schedule_calendars(sender, instance, created, **kwargs):
    """Ensure every new user immediately gets the two default calendars."""
    if not created:
        return

    try:
        ScheduleService.ensure_default_calendars(instance)
        logger.info("Created default schedule calendars for user %s", instance.email)
    except Exception as exc:
        logger.error("Failed to create default schedule calendars for %s: %s", instance.email, exc)

