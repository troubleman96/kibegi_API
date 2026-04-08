import io
import logging
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from .models import ScheduleCalendar, ScheduleEvent, ScheduleSyncAccessLog

logger = logging.getLogger("kibegi")


WEEKDAY_TO_ICS = {
    "monday": "MO",
    "tuesday": "TU",
    "wednesday": "WE",
    "thursday": "TH",
    "friday": "FR",
    "saturday": "SA",
    "sunday": "SU",
}


class ScheduleService:
    """Service helpers for calendar bootstrap, sharing, and export."""

    DEFAULT_CALENDARS = (
        (ScheduleCalendar.CALENDAR_TYPE_CLASSES, "My Classes"),
        (ScheduleCalendar.CALENDAR_TYPE_EXAMINATION, "My Examinations"),
    )

    @classmethod
    def ensure_default_calendars(cls, user):
        """Create missing default calendars for a user without duplicating existing ones."""
        calendars = []
        with transaction.atomic():
            for calendar_type, default_name in cls.DEFAULT_CALENDARS:
                calendar, _ = ScheduleCalendar.objects.get_or_create(
                    owner=user,
                    calendar_type=calendar_type,
                    defaults={
                        "name": default_name,
                        "description": f"Default {calendar_type} schedule for {user.full_name}.",
                    },
                )
                calendars.append(calendar)
        return calendars

    @classmethod
    def get_user_calendars(cls, user):
        """Return the user's calendars after ensuring defaults exist."""
        cls.ensure_default_calendars(user)
        return ScheduleCalendar.objects.filter(owner=user).prefetch_related("events").order_by("calendar_type")

    @staticmethod
    def build_public_url(request, route_name, **kwargs):
        """Build an absolute URL for public schedule routes."""
        return request.build_absolute_uri(reverse(route_name, kwargs=kwargs))

    @classmethod
    def build_share_payload(cls, request, calendar):
        """Return all URLs the frontend needs to sync or open a calendar."""
        subscribe_url = cls.build_public_url(
            request,
            "schedule_public_subscribe",
            token=calendar.share_token,
        )
        download_url = cls.build_public_url(
            request,
            "schedule_public_download",
            token=calendar.share_token,
        )
        info_url = cls.build_public_url(
            request,
            "schedule_public_info",
            token=calendar.share_token,
        )
        code_info_url = cls.build_public_url(
            request,
            "schedule_public_code_info",
            code=calendar.calendar_code,
        )
        webcal_url = subscribe_url.replace("https://", "webcal://", 1) if subscribe_url.startswith("https://") else subscribe_url.replace("http://", "webcal://", 1)

        frontend_base = getattr(settings, "SCHEDULE_FRONTEND_URL", "").rstrip("/")
        frontend_subscription_url = (
            f"{frontend_base}/subscribe/{calendar.share_token}" if frontend_base else None
        )

        return {
            "calendar_id": str(calendar.id),
            "calendar_type": calendar.calendar_type,
            "calendar_code": calendar.calendar_code,
            "subscribe_url": subscribe_url,
            "download_url": download_url,
            "webcal_url": webcal_url,
            "subscription_page_url": info_url,
            "frontend_subscription_url": frontend_subscription_url,
            "code_lookup_url": code_info_url,
        }

    @staticmethod
    def generate_ics(calendar, events: Iterable[ScheduleEvent]):
        """Generate a standards-friendly ICS payload for a calendar."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Kibegi//Schedule//EN",
            f"X-WR-CALNAME:{calendar.name}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-PUBLISHED-TTL:PT15M",
            "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        ]

        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@kibegi.com",
                    f"DTSTAMP:{event.updated_at.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTSTART:{event.start_at.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTEND:{event.end_at.strftime('%Y%m%dT%H%M%SZ')}",
                    f"SUMMARY:{event.title}",
                ]
            )

            if event.description:
                lines.append(f"DESCRIPTION:{event.description}")
            if event.location:
                lines.append(f"LOCATION:{event.location}")

            if event.recurrence == ScheduleEvent.RECURRENCE_DAILY:
                lines.append("RRULE:FREQ=DAILY")
            elif event.recurrence == ScheduleEvent.RECURRENCE_MONTHLY:
                lines.append("RRULE:FREQ=MONTHLY")
            elif event.recurrence == ScheduleEvent.RECURRENCE_WEEKLY and event.days:
                byday = ",".join(
                    WEEKDAY_TO_ICS[day.lower()]
                    for day in event.days
                    if day and day.lower() in WEEKDAY_TO_ICS
                )
                if byday:
                    lines.append(f"RRULE:FREQ=WEEKLY;BYDAY={byday}")

            if event.reminder_minutes:
                lines.extend(
                    [
                        "BEGIN:VALARM",
                        "ACTION:DISPLAY",
                        f"DESCRIPTION:Reminder for {event.title}",
                        f"TRIGGER:-PT{event.reminder_minutes}M",
                        "END:VALARM",
                    ]
                )

            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    @staticmethod
    def generate_qr_png(url: str):
        """Generate a QR code PNG for a public share URL."""
        import qrcode

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def record_public_access(calendar, request, access_type: str):
        """Log public sync activity without letting logging failures break the endpoint."""
        try:
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")
            ScheduleSyncAccessLog.objects.create(
                calendar=calendar,
                access_type=access_type,
                ip_address=ip_address or None,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except Exception as exc:
            logger.warning("Failed to record schedule public access: %s", exc)

