from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from datetime import timedelta
from unittest.mock import patch

from .models import ScheduleCalendar, ScheduleEvent, ScheduleSmsAccount, ScheduleSmsDeliveryLog, ScheduleSyncAccessLog

User = get_user_model()


@override_settings(
    SCHEDULE_FRONTEND_URL="https://app.kibegi.com/schedule",
    ALLOWED_HOSTS=["testserver", "api.kibegi.test"],
)
class ScheduleAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="schedule@test.com",
            password="StrongPass123!",
            full_name="Schedule User",
            user_type="student",
        )
        self.other_user = User.objects.create_user(
            email="other-schedule@test.com",
            password="StrongPass123!",
            full_name="Other Schedule User",
            user_type="lecturer",
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.anon_client = APIClient()

        self.classes_calendar = ScheduleCalendar.objects.get(
            owner=self.user,
            calendar_type=ScheduleCalendar.CALENDAR_TYPE_CLASSES,
        )
        self.examination_calendar = ScheduleCalendar.objects.get(
            owner=self.user,
            calendar_type=ScheduleCalendar.CALENDAR_TYPE_EXAMINATION,
        )
        self.other_classes_calendar = ScheduleCalendar.objects.get(
            owner=self.other_user,
            calendar_type=ScheduleCalendar.CALENDAR_TYPE_CLASSES,
        )

    def create_event(self, calendar=None, **overrides):
        calendar = calendar or self.classes_calendar
        payload = {
            "calendar": self.other_classes_calendar.id,
            "title": "Linear Algebra",
            "description": "Matrices and vectors",
            "location": "Room 4B",
            "start_at": "2026-05-01T09:00:00Z",
            "end_at": "2026-05-01T10:30:00Z",
            "event_type": ScheduleEvent.EVENT_TYPE_CLASS,
            "recurrence": ScheduleEvent.RECURRENCE_WEEKLY,
            "days": ["monday", "wednesday"],
            "reminder_minutes": 20,
        }
        payload.update(overrides)
        response = self.client.post(
            reverse("schedule_calendar_events", kwargs={"pk": calendar.pk}),
            payload,
            format="json",
        )
        return response

    def test_default_calendars_exist_for_new_user(self):
        calendars = ScheduleCalendar.objects.filter(owner=self.user).order_by("calendar_type")
        self.assertEqual(calendars.count(), 2)
        self.assertSetEqual(
            set(calendars.values_list("calendar_type", flat=True)),
            {
                ScheduleCalendar.CALENDAR_TYPE_CLASSES,
                ScheduleCalendar.CALENDAR_TYPE_EXAMINATION,
            },
        )

    def test_calendar_list_requires_authentication(self):
        response = self.anon_client.get(reverse("schedule_calendar_list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_calendar_list_returns_both_default_calendars_with_event_counts(self):
        ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Physics",
            start_at="2026-06-01T08:00:00Z",
            end_at="2026-06-01T10:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=10,
        )

        response = self.client.get(reverse("schedule_calendar_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Schedule calendars retrieved successfully")
        self.assertEqual(len(response.data["data"]), 2)

        calendars_by_type = {item["calendar_type"]: item for item in response.data["data"]}
        self.assertEqual(calendars_by_type["classes"]["event_count"], 1)
        self.assertEqual(calendars_by_type["examination"]["event_count"], 0)
        self.assertEqual(calendars_by_type["classes"]["calendar_code"], self.classes_calendar.calendar_code)

    def test_calendar_detail_returns_only_owned_calendar_with_nested_events(self):
        event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Discrete Math",
            description="Sets and logic",
            start_at="2026-06-02T09:00:00Z",
            end_at="2026-06-02T11:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=15,
        )

        response = self.client.get(
            reverse("schedule_calendar_detail", kwargs={"pk": self.classes_calendar.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.classes_calendar.id)
        self.assertEqual(response.data["data"]["event_count"], 1)
        self.assertEqual(len(response.data["data"]["events"]), 1)
        self.assertEqual(response.data["data"]["events"][0]["id"], event.id)

    def test_calendar_detail_for_other_users_calendar_returns_not_found(self):
        response = self.client.get(
            reverse("schedule_calendar_detail", kwargs={"pk": self.other_classes_calendar.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_calendar_patch_updates_allowed_fields_only(self):
        response = self.client.patch(
            reverse("schedule_calendar_detail", kwargs={"pk": self.classes_calendar.pk}),
            {
                "name": "Updated Classes",
                "description": "Updated calendar description",
                "is_public_sync": False,
                "calendar_type": ScheduleCalendar.CALENDAR_TYPE_EXAMINATION,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.classes_calendar.refresh_from_db()
        self.assertEqual(self.classes_calendar.name, "Updated Classes")
        self.assertEqual(self.classes_calendar.description, "Updated calendar description")
        self.assertFalse(self.classes_calendar.is_public_sync)
        self.assertEqual(self.classes_calendar.calendar_type, ScheduleCalendar.CALENDAR_TYPE_CLASSES)

    def test_calendar_events_list_returns_events_in_start_time_order(self):
        later_event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Later Class",
            start_at="2026-06-05T13:00:00Z",
            end_at="2026-06-05T14:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=15,
        )
        earlier_event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Earlier Class",
            start_at="2026-06-05T08:00:00Z",
            end_at="2026-06-05T09:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=15,
        )

        response = self.client.get(
            reverse("schedule_calendar_events", kwargs={"pk": self.classes_calendar.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["data"]],
            [earlier_event.id, later_event.id],
        )

    def test_create_event_persists_under_requested_calendar(self):
        response = self.create_event()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_event = ScheduleEvent.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(created_event.calendar, self.classes_calendar)
        self.assertEqual(created_event.source, ScheduleEvent.SOURCE_MANUAL)
        self.assertEqual(created_event.days, ["monday", "wednesday"])
        self.assertEqual(response.data["data"]["calendar"], self.classes_calendar.id)

    def test_create_event_rejects_invalid_time_range(self):
        response = self.create_event(
            start_at="2026-05-01T11:30:00Z",
            end_at="2026-05-01T10:30:00Z",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_at", response.data)

    def test_create_event_rejects_weekly_recurrence_without_days(self):
        response = self.create_event(days=[])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("days", response.data)

    def test_create_event_for_other_users_calendar_returns_not_found(self):
        response = self.client.post(
            reverse("schedule_calendar_events", kwargs={"pk": self.other_classes_calendar.pk}),
            {
                "title": "Unauthorized Event",
                "start_at": "2026-05-01T09:00:00Z",
                "end_at": "2026-05-01T10:30:00Z",
                "event_type": ScheduleEvent.EVENT_TYPE_CLASS,
                "recurrence": ScheduleEvent.RECURRENCE_NONE,
                "reminder_minutes": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_event_detail_update_and_delete_flow(self):
        event_response = self.create_event(location="Original Hall")
        event_id = event_response.data["data"]["id"]

        detail_response = self.client.get(reverse("schedule_event_detail", kwargs={"pk": event_id}))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["title"], "Linear Algebra")

        update_response = self.client.patch(
            reverse("schedule_event_detail", kwargs={"pk": event_id}),
            {
                "location": "Updated Hall",
                "recurrence": ScheduleEvent.RECURRENCE_MONTHLY,
                "days": None,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["location"], "Updated Hall")
        self.assertEqual(update_response.data["data"]["recurrence"], ScheduleEvent.RECURRENCE_MONTHLY)

        delete_response = self.client.delete(reverse("schedule_event_detail", kwargs={"pk": event_id}))
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delete_response.data["message"], "Schedule event deleted successfully")
        self.assertFalse(ScheduleEvent.objects.filter(pk=event_id).exists())

    def test_event_detail_for_other_users_event_returns_not_found(self):
        other_event = ScheduleEvent.objects.create(
            calendar=self.other_classes_calendar,
            title="Private Event",
            start_at="2026-06-10T08:00:00Z",
            end_at="2026-06-10T09:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_OTHER,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=10,
        )

        response = self.client.get(reverse("schedule_event_detail", kwargs={"pk": other_event.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_event_update_rejects_invalid_weekly_recurrence_without_days(self):
        event_response = self.create_event(recurrence=ScheduleEvent.RECURRENCE_NONE, days=None)
        event_id = event_response.data["data"]["id"]

        response = self.client.patch(
            reverse("schedule_event_detail", kwargs={"pk": event_id}),
            {"recurrence": ScheduleEvent.RECURRENCE_WEEKLY, "days": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("days", response.data)

    def test_share_endpoint_returns_expected_urls(self):
        response = self.client.get(
            reverse("schedule_calendar_share", kwargs={"pk": self.classes_calendar.pk}),
            HTTP_HOST="api.kibegi.test",
            secure=True,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["calendar_id"], str(self.classes_calendar.id))
        self.assertEqual(
            data["subscribe_url"],
            f"https://api.kibegi.test/api/v1/public/schedule/{self.classes_calendar.share_token}/subscribe/",
        )
        self.assertEqual(
            data["download_url"],
            f"https://api.kibegi.test/api/v1/public/schedule/{self.classes_calendar.share_token}/download/",
        )
        self.assertEqual(
            data["subscription_page_url"],
            f"https://api.kibegi.test/api/v1/public/schedule/{self.classes_calendar.share_token}/info/",
        )
        self.assertEqual(
            data["webcal_url"],
            f"webcal://api.kibegi.test/api/v1/public/schedule/{self.classes_calendar.share_token}/subscribe/",
        )
        self.assertEqual(
            data["frontend_subscription_url"],
            f"https://app.kibegi.com/schedule/subscribe/{self.classes_calendar.share_token}",
        )
        self.assertEqual(
            data["code_lookup_url"],
            f"https://api.kibegi.test/api/v1/public/schedule/code/{self.classes_calendar.calendar_code}/info/",
        )

    def test_share_endpoint_returns_not_found_for_unowned_calendar(self):
        response = self.client.get(
            reverse("schedule_calendar_share", kwargs={"pk": self.other_classes_calendar.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Schedule calendar not found")

    def test_qr_endpoint_returns_png_binary(self):
        response = self.client.get(
            reverse("schedule_calendar_qr", kwargs={"pk": self.classes_calendar.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertGreater(len(response.content), 100)

    def test_public_info_and_code_lookup_return_calendar_metadata_and_log_access(self):
        ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Physics",
            start_at="2026-06-01T08:00:00Z",
            end_at="2026-06-01T10:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=10,
        )

        info_response = self.anon_client.get(
            reverse("schedule_public_info", kwargs={"token": self.classes_calendar.share_token}),
            HTTP_HOST="api.kibegi.test",
            secure=True,
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.1",
            HTTP_USER_AGENT="ScheduleTester/1.0",
        )
        self.assertEqual(info_response.status_code, status.HTTP_200_OK)
        self.assertEqual(info_response.data["data"]["calendar_code"], self.classes_calendar.calendar_code)
        self.assertEqual(info_response.data["data"]["event_count"], 1)

        code_info_response = self.anon_client.get(
            reverse("schedule_public_code_info", kwargs={"code": self.classes_calendar.calendar_code.lower()}),
            HTTP_HOST="api.kibegi.test",
            secure=True,
        )
        self.assertEqual(code_info_response.status_code, status.HTTP_200_OK)
        self.assertEqual(code_info_response.data["data"]["calendar_type"], self.classes_calendar.calendar_type)

        log_entries = ScheduleSyncAccessLog.objects.filter(calendar=self.classes_calendar).order_by("accessed_at")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.first().access_type, "info")
        self.assertEqual(log_entries.first().ip_address, "203.0.113.10")
        self.assertEqual(log_entries.first().user_agent, "ScheduleTester/1.0")
        self.assertEqual(log_entries.last().access_type, "code-info")

    def test_public_subscribe_and_download_return_ics_and_log_access(self):
        event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="Public Chemistry",
            description="Lab safety briefing",
            location="Lab 2",
            start_at="2026-06-12T07:00:00Z",
            end_at="2026-06-12T09:00:00Z",
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_WEEKLY,
            days=["friday"],
            reminder_minutes=30,
        )

        subscribe_response = self.anon_client.get(
            reverse("schedule_public_subscribe", kwargs={"token": self.classes_calendar.share_token})
        )
        self.assertEqual(subscribe_response.status_code, status.HTTP_200_OK)
        self.assertIn("inline;", subscribe_response["Content-Disposition"])
        subscribe_text = subscribe_response.content.decode("utf-8")
        self.assertIn("BEGIN:VCALENDAR", subscribe_text)
        self.assertIn(f"UID:{event.id}@kibegi.com", subscribe_text)
        self.assertIn("SUMMARY:Public Chemistry", subscribe_text)
        self.assertIn("RRULE:FREQ=WEEKLY;BYDAY=FR", subscribe_text)
        self.assertIn("TRIGGER:-PT30M", subscribe_text)

        download_response = self.anon_client.get(
            reverse("schedule_public_download", kwargs={"token": self.classes_calendar.share_token})
        )
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment;", download_response["Content-Disposition"])
        self.assertIn("BEGIN:VCALENDAR", download_response.content.decode("utf-8"))

        access_types = list(
            ScheduleSyncAccessLog.objects.filter(calendar=self.classes_calendar)
            .order_by("accessed_at")
            .values_list("access_type", flat=True)
        )
        self.assertEqual(access_types, ["subscribe", "download"])

    def test_public_endpoints_return_not_found_for_unknown_or_private_calendar(self):
        self.classes_calendar.is_public_sync = False
        self.classes_calendar.save(update_fields=["is_public_sync"])

        info_response = self.anon_client.get(
            reverse("schedule_public_info", kwargs={"token": self.classes_calendar.share_token})
        )
        subscribe_response = self.anon_client.get(
            reverse("schedule_public_subscribe", kwargs={"token": self.classes_calendar.share_token})
        )
        download_response = self.anon_client.get(
            reverse("schedule_public_download", kwargs={"token": self.classes_calendar.share_token})
        )
        code_info_response = self.anon_client.get(
            reverse("schedule_public_code_info", kwargs={"code": self.classes_calendar.calendar_code})
        )

        for response in [info_response, subscribe_response, download_response, code_info_response]:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            if hasattr(response, "data"):
                self.assertEqual(response.data["message"], "Schedule calendar not found")

    def test_unknown_authenticated_resources_return_not_found(self):
        calendar_response = self.client.get(reverse("schedule_calendar_detail", kwargs={"pk": 999999}))
        events_response = self.client.get(reverse("schedule_calendar_events", kwargs={"pk": 999999}))
        event_response = self.client.get(reverse("schedule_event_detail", kwargs={"pk": 999999}))

        self.assertEqual(calendar_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(events_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(event_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sms_account_endpoint_returns_and_updates_wallet(self):
        response = self.client.get(reverse("schedule_sms_account"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["balance_credits"], 0)

        update_response = self.client.patch(
            reverse("schedule_sms_account"),
            {"phone_number": "+254700000000", "sender_id": "KIBEGI"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["phone_number"], "+254700000000")
        self.assertEqual(update_response.data["data"]["sender_id"], "KIBEGI")

    @override_settings(
        AFRICASTALKING_USERNAME="test-user",
        AFRICASTALKING_API_KEY="test-key",
        AFRICASTALKING_SENDER_ID="KIBEGI",
        SCHEDULE_SMS_COST_PER_MESSAGE=1,
        SCHEDULE_SMS_GRACE_MINUTES=15,
        SCHEDULE_SMS_LOOKAHEAD_DAYS=7,
    )
    def test_sms_reminder_command_consumes_credit_and_logs_delivery(self):
        account = ScheduleSmsAccount.objects.create(
            owner=self.user,
            phone_number="+254700000000",
            balance_credits=2,
            sender_id="KIBEGI",
        )
        event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="SMS Reminder Class",
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=60,
        )

        with patch("apps.schedule.management.commands.send_schedule_sms_reminders.AfricasTalkingSmsClient") as mock_client_class, patch(
            "apps.schedule.services.EmailMultiAlternatives"
        ) as mock_email_class:
            mock_client = mock_client_class.return_value
            mock_client.send_sms.return_value = {
                "provider_message_id": "msg-123",
                "raw_response": {"ok": True},
            }
            mock_email = mock_email_class.return_value
            call_command("send_schedule_sms_reminders")

        account.refresh_from_db()
        self.assertEqual(account.balance_credits, 1)
        log = ScheduleSmsDeliveryLog.objects.get(event=event)
        self.assertEqual(log.status, ScheduleSmsDeliveryLog.STATUS_SENT)
        self.assertEqual(log.provider_message_id, "msg-123")
        self.assertEqual(log.recipient_phone, "+254700000000")
        mock_email_class.assert_called_once()
        mock_email.attach_alternative.assert_called_once()
        mock_email.send.assert_called_once()

    @override_settings(
        AFRICASTALKING_USERNAME="test-user",
        AFRICASTALKING_API_KEY="test-key",
        SCHEDULE_SMS_COST_PER_MESSAGE=1,
        SCHEDULE_SMS_GRACE_MINUTES=15,
        SCHEDULE_SMS_LOOKAHEAD_DAYS=7,
    )
    def test_sms_reminder_command_skips_when_credits_are_missing(self):
        ScheduleSmsAccount.objects.create(
            owner=self.user,
            phone_number="+254700000000",
            balance_credits=0,
        )
        event = ScheduleEvent.objects.create(
            calendar=self.classes_calendar,
            title="No Credits Class",
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
            event_type=ScheduleEvent.EVENT_TYPE_CLASS,
            recurrence=ScheduleEvent.RECURRENCE_NONE,
            reminder_minutes=60,
        )

        with patch("apps.schedule.services.EmailMultiAlternatives") as mock_email_class:
            mock_email = mock_email_class.return_value
            call_command("send_schedule_sms_reminders", dry_run=False)

        log = ScheduleSmsDeliveryLog.objects.get(event=event)
        self.assertEqual(log.status, ScheduleSmsDeliveryLog.STATUS_SKIPPED)
        self.assertIn("Insufficient SMS credits", log.error_message)
        mock_email_class.assert_called_once()
        mock_email.send.assert_called_once()
