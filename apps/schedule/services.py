import io
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from .models import ScheduleCalendar, ScheduleEvent, ScheduleSmsAccount, ScheduleSmsDeliveryLog, ScheduleSyncAccessLog

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


class AfricasTalkingSmsClient:
    """Small adapter around Africa's Talking SMS API."""

    def __init__(self):
        self.username = getattr(settings, "AFRICASTALKING_USERNAME", "")
        self.api_key = getattr(settings, "AFRICASTALKING_API_KEY", "")
        self.sender_id = getattr(settings, "AFRICASTALKING_SENDER_ID", "")
        self.messaging_url = getattr(
            settings,
            "AFRICASTALKING_SMS_URL",
            "https://api.africastalking.com/version1/messaging",
        )

    def is_configured(self):
        return bool(self.username and self.api_key)

    def send_sms(self, phone_number: str, message: str, sender_id: str = ""):
        if not self.is_configured():
            raise RuntimeError("Africa's Talking SMS settings are not configured.")

        payload = {
            "username": self.username,
            "to": phone_number,
            "message": message,
        }
        active_sender = sender_id or self.sender_id
        if active_sender:
            payload["from"] = active_sender

        encoded_payload = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(self.messaging_url, data=encoded_payload, method="POST")
        request.add_header("apiKey", self.api_key)
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise RuntimeError(f"Africa's Talking SMS request failed: {exc.code} {error_body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Africa's Talking SMS request failed: {exc.reason}") from exc

        try:
            response_data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Africa's Talking SMS returned invalid JSON.") from exc

        recipients = response_data.get("SMSMessageData", {}).get("Recipients", [])
        recipient = recipients[0] if recipients else {}
        return {
            "provider_message_id": recipient.get("messageId", ""),
            "raw_response": response_data,
        }


class ScheduleSmsService:
    """Dispatch schedule reminder SMS messages and manage credits."""

    @staticmethod
    def get_account_for_user(user):
        account, _ = ScheduleSmsAccount.objects.get_or_create(owner=user)
        return account

    @staticmethod
    def build_reminder_message(event: ScheduleEvent):
        start_time = timezone.localtime(event.start_at)
        when = start_time.strftime("%a, %d %b %Y at %I:%M %p")
        parts = [f"Kibegi reminder: {event.title}", f"starts on {when}"]
        if event.location:
            parts.append(f"Location: {event.location}")
        return " | ".join(parts)

    @staticmethod
    def get_due_events(now=None):
        now = now or timezone.now()
        grace_minutes = getattr(settings, "SCHEDULE_SMS_GRACE_MINUTES", 10)
        lookahead_days = getattr(settings, "SCHEDULE_SMS_LOOKAHEAD_DAYS", 7)
        lower_bound = now - timedelta(minutes=grace_minutes)
        upper_bound = now + timedelta(days=lookahead_days)
        candidates = (
            ScheduleEvent.objects.select_related("calendar", "calendar__owner")
            .filter(start_at__gte=lower_bound, start_at__lte=upper_bound)
            .order_by("start_at")
        )
        due_events = []
        for event in candidates:
            if hasattr(event, "sms_delivery_log"):
                continue
            reminder_at = event.reminder_at
            reminder_deadline = reminder_at + timedelta(minutes=grace_minutes)
            if reminder_at <= now <= reminder_deadline:
                due_events.append(event)
        return due_events

    @classmethod
    def dispatch_reminder(cls, event: ScheduleEvent, client=None, now=None, dry_run=False):
        now = now or timezone.now()
        client = client or AfricasTalkingSmsClient()
        cost_per_message = getattr(settings, "SCHEDULE_SMS_COST_PER_MESSAGE", 1)
        message = cls.build_reminder_message(event)
        account = cls.get_account_for_user(event.calendar.owner)

        if not account.is_active:
            return ScheduleSmsDeliveryLog.objects.create(
                event=event,
                sms_account=account,
                recipient_phone=account.phone_number,
                provider_name=account.provider_name,
                status=ScheduleSmsDeliveryLog.STATUS_SKIPPED,
                message=message,
                credits_used=0,
                error_message="SMS account is inactive.",
                sent_at=now,
            )

        if not account.phone_number:
            return ScheduleSmsDeliveryLog.objects.create(
                event=event,
                sms_account=account,
                recipient_phone="",
                provider_name=account.provider_name,
                status=ScheduleSmsDeliveryLog.STATUS_SKIPPED,
                message=message,
                credits_used=0,
                error_message="No destination phone number is configured.",
                sent_at=now,
            )

        if account.balance_credits < cost_per_message:
            return ScheduleSmsDeliveryLog.objects.create(
                event=event,
                sms_account=account,
                recipient_phone=account.phone_number,
                provider_name=account.provider_name,
                status=ScheduleSmsDeliveryLog.STATUS_SKIPPED,
                message=message,
                credits_used=0,
                error_message="Insufficient SMS credits.",
                sent_at=now,
            )

        if dry_run:
            return ScheduleSmsDeliveryLog(
                event=event,
                sms_account=account,
                recipient_phone=account.phone_number,
                provider_name=account.provider_name,
                status=ScheduleSmsDeliveryLog.STATUS_PENDING,
                message=message,
                credits_used=cost_per_message,
                sent_at=None,
            )

        try:
            provider_result = client.send_sms(
                phone_number=account.phone_number,
                message=message,
                sender_id=account.sender_id,
            )
        except Exception as exc:
            return ScheduleSmsDeliveryLog.objects.create(
                event=event,
                sms_account=account,
                recipient_phone=account.phone_number,
                provider_name=account.provider_name,
                status=ScheduleSmsDeliveryLog.STATUS_FAILED,
                message=message,
                credits_used=0,
                error_message=str(exc),
                sent_at=now,
            )

        with transaction.atomic():
            account = ScheduleSmsAccount.objects.select_for_update().get(pk=account.pk)
            if account.balance_credits < cost_per_message:
                return ScheduleSmsDeliveryLog.objects.create(
                    event=event,
                    sms_account=account,
                    recipient_phone=account.phone_number,
                    provider_name=account.provider_name,
                    status=ScheduleSmsDeliveryLog.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message="Insufficient SMS credits.",
                    sent_at=now,
                )

            account.balance_credits -= cost_per_message
            account.save(update_fields=["balance_credits", "updated_at"])
            return ScheduleSmsDeliveryLog.objects.create(
                event=event,
                sms_account=account,
                recipient_phone=account.phone_number,
                provider_name=account.provider_name,
                provider_message_id=provider_result.get("provider_message_id", ""),
                status=ScheduleSmsDeliveryLog.STATUS_SENT,
                message=message,
                credits_used=cost_per_message,
                provider_response=provider_result.get("raw_response"),
                sent_at=now,
            )

    @classmethod
    def dispatch_due_reminders(cls, client=None, now=None, limit=None, dry_run=False):
        due_events = cls.get_due_events(now=now)
        if limit is not None:
            due_events = due_events[:limit]

        results = {
            "due": len(due_events),
            "sent": 0,
            "failed": 0,
            "skipped": 0,
        }

        for event in due_events:
            log = cls.dispatch_reminder(event, client=client, now=now, dry_run=dry_run)
            if log.status == ScheduleSmsDeliveryLog.STATUS_SENT:
                results["sent"] += 1
            elif log.status == ScheduleSmsDeliveryLog.STATUS_FAILED:
                results["failed"] += 1
            else:
                results["skipped"] += 1

        return results

