from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import ScheduleCalendar, ScheduleEvent
from .services import ScheduleService

User = get_user_model()


class ScheduleAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="schedule@test.com",
            password="StrongPass123!",
            full_name="Schedule User",
            user_type="student",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_default_calendars_exist_for_new_user(self):
        calendars = ScheduleCalendar.objects.filter(owner=self.user).order_by("calendar_type")
        self.assertEqual(calendars.count(), 2)
        self.assertSetEqual(set(calendars.values_list("calendar_type", flat=True)), {"classes", "examination"})

    def test_calendar_list_event_crud_and_share_flow(self):
        list_response = self.client.get("/api/v1/schedule/calendars/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["data"]), 2)

        classes_calendar_id = next(
            item["id"] for item in list_response.data["data"] if item["calendar_type"] == "classes"
        )

        create_response = self.client.post(
            f"/api/v1/schedule/calendars/{classes_calendar_id}/events/",
            {
                "title": "Linear Algebra",
                "description": "Matrices and vectors",
                "location": "Room 4B",
                "start_at": "2026-05-01T09:00:00Z",
                "end_at": "2026-05-01T10:30:00Z",
                "event_type": "class",
                "recurrence": "weekly",
                "days": ["monday", "wednesday"],
                "reminder_minutes": 20,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        event_id = create_response.data["data"]["id"]

        events_response = self.client.get(f"/api/v1/schedule/calendars/{classes_calendar_id}/events/")
        self.assertEqual(events_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(events_response.data["data"]), 1)

        patch_response = self.client.patch(
            f"/api/v1/schedule/events/{event_id}/",
            {"location": "Updated Hall"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["data"]["location"], "Updated Hall")

        share_response = self.client.get(f"/api/v1/schedule/calendars/{classes_calendar_id}/share/")
        self.assertEqual(share_response.status_code, status.HTTP_200_OK)
        self.assertIn("subscribe_url", share_response.data["data"])
        self.assertIn("download_url", share_response.data["data"])
        self.assertIn("frontend_subscription_url", share_response.data["data"])

        qr_response = self.client.get(f"/api/v1/schedule/calendars/{classes_calendar_id}/qr/")
        self.assertEqual(qr_response.status_code, status.HTTP_200_OK)
        self.assertEqual(qr_response["Content-Type"], "image/png")

        delete_response = self.client.delete(f"/api/v1/schedule/events/{event_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(ScheduleEvent.objects.filter(pk=event_id).exists())

    def test_public_info_subscribe_and_download_endpoints(self):
        calendar = ScheduleCalendar.objects.get(owner=self.user, calendar_type="classes")
        ScheduleEvent.objects.create(
            calendar=calendar,
            title="Physics",
            start_at="2026-06-01T08:00:00Z",
            end_at="2026-06-01T10:00:00Z",
            event_type="class",
            recurrence="none",
            reminder_minutes=10,
        )

        anon_client = APIClient()
        info_response = anon_client.get(f"/api/v1/public/schedule/{calendar.share_token}/info/")
        self.assertEqual(info_response.status_code, status.HTTP_200_OK)
        self.assertEqual(info_response.data["data"]["calendar_code"], calendar.calendar_code)

        code_info_response = anon_client.get(f"/api/v1/public/schedule/code/{calendar.calendar_code}/info/")
        self.assertEqual(code_info_response.status_code, status.HTTP_200_OK)

        subscribe_response = anon_client.get(f"/api/v1/public/schedule/{calendar.share_token}/subscribe/")
        self.assertEqual(subscribe_response.status_code, status.HTTP_200_OK)
        self.assertIn("BEGIN:VCALENDAR", subscribe_response.content.decode("utf-8"))

        download_response = anon_client.get(f"/api/v1/public/schedule/{calendar.share_token}/download/")
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment;", download_response["Content-Disposition"])
