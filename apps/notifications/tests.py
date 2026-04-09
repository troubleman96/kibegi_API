"""
Integration tests for notification triggers across apps.

Run with:
    venv/bin/python manage.py test apps.notifications --settings=kibegi_api.test_settings
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.classes.models import Class, Membership
from apps.notifications.models import Notification
from apps.uploads.models import Upload


User = get_user_model()


class NotificationTriggerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "test123"

        self.lecturer = User.objects.create_user(
            email="lecturer@test.com",
            password=self.password,
            full_name="Dr. Smith",
            user_type="lecturer",
        )
        self.student1 = User.objects.create_user(
            email="student1@test.com",
            password=self.password,
            full_name="John Doe",
            user_type="student",
        )
        self.student2 = User.objects.create_user(
            email="student2@test.com",
            password=self.password,
            full_name="Jane Smith",
            user_type="student",
        )

        self.class_obj = Class.objects.create(
            name="Computer Science 101",
            description="Intro to CS",
            creator=self.lecturer,
            is_verified=True,
        )
        Membership.objects.create(user=self.lecturer, class_obj=self.class_obj, role="lecturer")
        Membership.objects.create(user=self.student1, class_obj=self.class_obj, role="student")
        Membership.objects.create(user=self.student2, class_obj=self.class_obj, role="student")

        self.upload = Upload.objects.create(
            file_name="test_document.pdf",
            file=SimpleUploadedFile("test_document.pdf", b"file_content", content_type="application/pdf"),
            file_size=len(b"file_content"),
            file_type="document",
            uploader=self.student1,
            class_obj=self.class_obj,
        )

    def authenticate(self, user):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["data"]["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_share_create_triggers_share_request_notification(self):
        self.authenticate(self.student1)

        response = self.client.post(
            "/api/v1/sharing/",
            {"file_code": self.upload.file_code, "shared_with_id": self.student2.id, "message": "Here you go"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        share_id = response.data["data"]["id"]
        self.assertTrue(
            Notification.objects.filter(
                user=self.student2,
                notification_type="share_request",
                related_object_id=str(share_id),
            ).exists()
        )

    def test_share_accept_triggers_share_accepted_notification(self):
        self.authenticate(self.student1)
        create_response = self.client.post(
            "/api/v1/sharing/",
            {"file_code": self.upload.file_code, "shared_with_id": self.student2.id},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        share_id = create_response.data["data"]["id"]

        self.authenticate(self.student2)
        accept_response = self.client.post(f"/api/v1/sharing/{share_id}/accept/", format="json")
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)

        self.assertTrue(
            Notification.objects.filter(
                user=self.student1,
                notification_type="share_accepted",
                related_object_id=str(share_id),
            ).exists()
        )

    def test_share_reject_triggers_share_rejected_notification(self):
        self.authenticate(self.student1)
        create_response = self.client.post(
            "/api/v1/sharing/",
            {"file_code": self.upload.file_code, "shared_with_id": self.student2.id},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        share_id = create_response.data["data"]["id"]

        self.authenticate(self.student2)
        reject_response = self.client.post(f"/api/v1/sharing/{share_id}/reject/", format="json")
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)

        self.assertTrue(
            Notification.objects.filter(
                user=self.student1,
                notification_type="share_rejected",
                related_object_id=str(share_id),
            ).exists()
        )

    def test_friend_request_and_accept_triggers_notifications(self):
        self.authenticate(self.student1)
        create_response = self.client.post(
            "/api/v1/friends/add/",
            {"user_id": self.student2.id},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        friendship_id = create_response.data["data"]["id"]

        self.assertTrue(
            Notification.objects.filter(
                user=self.student2,
                notification_type="friend_request",
                related_object_id=str(friendship_id),
            ).exists()
        )

        self.authenticate(self.student2)
        accept_response = self.client.post(f"/api/v1/friends/{friendship_id}/accept/", format="json")
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)

        self.assertTrue(
            Notification.objects.filter(
                user=self.student1,
                notification_type="friend_accepted",
                related_object_id=str(friendship_id),
            ).exists()
        )

    def test_upload_create_triggers_upload_created_notifications(self):
        self.authenticate(self.student1)

        test_file = SimpleUploadedFile("new_upload.pdf", b"abc", content_type="application/pdf")
        response = self.client.post(
            "/api/v1/uploads/",
            {"file": test_file, "class_obj": str(self.class_obj.id)},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        upload_id = response.data["data"]["id"]

        self.assertTrue(
            Notification.objects.filter(
                user=self.student2,
                notification_type="upload_created",
                related_object_id=str(upload_id),
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.lecturer,
                notification_type="upload_created",
                related_object_id=str(upload_id),
            ).exists()
        )

    def test_class_join_triggers_class_joined_notifications(self):
        joiner = User.objects.create_user(
            email="joiner@test.com",
            password=self.password,
            full_name="New Student",
            user_type="student",
        )
        self.authenticate(joiner)

        response = self.client.post(
            "/api/v1/classes/join/",
            {"class_code": self.class_obj.class_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(
            Notification.objects.filter(
                user=self.lecturer,
                notification_type="class_joined",
                related_object_id=str(self.class_obj.id),
            ).exists()
        )

    def test_unread_count_endpoint(self):
        Notification.objects.create(
            user=self.student1,
            notification_type="friend_request",
            content="Test",
            related_object_id="1",
        )
        Notification.objects.create(
            user=self.student1,
            notification_type="friend_request",
            content="Test 2",
            related_object_id="2",
            is_read=True,
        )

        self.authenticate(self.student1)
        response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["unread_count"], 1)

