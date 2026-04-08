import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


CALENDAR_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CALENDAR_CODE_LENGTH = 6


def generate_share_token():
    """Generate a high-entropy public token for a calendar."""
    return secrets.token_urlsafe(32)


def generate_calendar_code():
    """Generate a short human-readable code for a calendar."""
    return "".join(secrets.choice(CALENDAR_CODE_ALPHABET) for _ in range(CALENDAR_CODE_LENGTH))


class ScheduleCalendar(models.Model):
    """A user-owned schedule calendar that groups related events."""

    CALENDAR_TYPE_CLASSES = "classes"
    CALENDAR_TYPE_EXAMINATION = "examination"
    CALENDAR_TYPE_CHOICES = (
        (CALENDAR_TYPE_CLASSES, "Classes"),
        (CALENDAR_TYPE_EXAMINATION, "Examination"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_calendars",
        help_text="The Kibegi user who owns this calendar.",
    )
    name = models.CharField(max_length=255, help_text="Display name shown in the UI.")
    calendar_type = models.CharField(
        max_length=20,
        choices=CALENDAR_TYPE_CHOICES,
        help_text="System calendar type. One per user for each type.",
    )
    description = models.TextField(blank=True, null=True, help_text="Optional description.")
    is_public_sync = models.BooleanField(
        default=True,
        help_text="Whether public token-based subscribe/download endpoints are enabled.",
    )
    share_token = models.CharField(
        max_length=255,
        unique=True,
        default=generate_share_token,
        help_text="Stable token used for public sync URLs.",
    )
    calendar_code = models.CharField(
        max_length=CALENDAR_CODE_LENGTH,
        unique=True,
        editable=False,
        help_text="Short manual code used for calendar lookup.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["calendar_type", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "calendar_type"],
                name="unique_schedule_calendar_type_per_owner",
            )
        ]

    def __str__(self):
        return f"{self.owner.email} - {self.name}"

    def save(self, *args, **kwargs):
        # Keep the short code stable once generated.
        if not self.calendar_code:
            self.calendar_code = self._generate_unique_calendar_code()
        if not self.share_token:
            self.share_token = generate_share_token()
        super().save(*args, **kwargs)

    def _generate_unique_calendar_code(self):
        # Generate until we find a free code. The code space is large enough
        # for this loop to stay fast in practice.
        code = generate_calendar_code()
        while ScheduleCalendar.objects.filter(calendar_code=code).exists():
            code = generate_calendar_code()
        return code


class ScheduleEvent(models.Model):
    """A calendar event that can be synced to external calendar clients."""

    RECURRENCE_NONE = "none"
    RECURRENCE_DAILY = "daily"
    RECURRENCE_WEEKLY = "weekly"
    RECURRENCE_MONTHLY = "monthly"
    RECURRENCE_CHOICES = (
        (RECURRENCE_NONE, "None"),
        (RECURRENCE_DAILY, "Daily"),
        (RECURRENCE_WEEKLY, "Weekly"),
        (RECURRENCE_MONTHLY, "Monthly"),
    )

    EVENT_TYPE_CLASS = "class"
    EVENT_TYPE_EXAM = "exam"
    EVENT_TYPE_STUDY = "study"
    EVENT_TYPE_DEADLINE = "deadline"
    EVENT_TYPE_MEETING = "meeting"
    EVENT_TYPE_OTHER = "other"
    EVENT_TYPE_CHOICES = (
        (EVENT_TYPE_CLASS, "Class"),
        (EVENT_TYPE_EXAM, "Exam"),
        (EVENT_TYPE_STUDY, "Study"),
        (EVENT_TYPE_DEADLINE, "Deadline"),
        (EVENT_TYPE_MEETING, "Meeting"),
        (EVENT_TYPE_OTHER, "Other"),
    )

    SOURCE_MANUAL = "manual"
    SOURCE_IMPORT = "import"
    SOURCE_SYSTEM = "system"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_IMPORT, "Import"),
        (SOURCE_SYSTEM, "System"),
    )

    calendar = models.ForeignKey(
        ScheduleCalendar,
        on_delete=models.CASCADE,
        related_name="events",
        help_text="Calendar the event belongs to.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    start_at = models.DateTimeField(help_text="When the event starts.")
    end_at = models.DateTimeField(help_text="When the event ends.")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default=EVENT_TYPE_OTHER)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE)
    days = models.JSONField(blank=True, null=True, help_text="List of weekdays for weekly recurrence.")
    reminder_minutes = models.PositiveIntegerField(default=15)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "created_at"]
        indexes = [
            models.Index(fields=["calendar", "start_at"]),
            models.Index(fields=["calendar", "event_type"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.calendar.name})"

    def clean(self):
        # Keep event time validation strict so sync feeds remain valid.
        if self.end_at <= self.start_at:
            raise ValidationError({"end_at": "End time must be after start time."})

        if self.recurrence == self.RECURRENCE_WEEKLY and not self.days:
            raise ValidationError({"days": "Weekly recurring events must include at least one day."})

    @property
    def duration(self):
        return self.end_at - self.start_at

    @property
    def reminder_at(self):
        return self.start_at - timedelta(minutes=self.reminder_minutes)


class ScheduleSyncAccessLog(models.Model):
    """Optional log of public schedule feed usage for observability."""

    calendar = models.ForeignKey(
        ScheduleCalendar,
        on_delete=models.CASCADE,
        related_name="sync_access_logs",
    )
    access_type = models.CharField(max_length=20, help_text="subscribe, download, info, qr")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accessed_at"]

    def __str__(self):
        return f"{self.calendar.calendar_code} {self.access_type} @ {timezone.localtime(self.accessed_at)}"

