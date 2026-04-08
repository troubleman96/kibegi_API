"""
Integration tests for the sharing app.

Run with:
    python manage.py test sharing.tests --settings=kibegi_api.test_settings
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.classes.models import Class, Membership
from apps.sharing.models import SharedFile
from apps.sharing.services import SharingService
from apps.uploads.models import Upload

User = get_user_model()


class SharingEndpointTests(TestCase):
    def setUp(self):
        self.password = "test123"
        self.client = APIClient()

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
        self.student3 = User.objects.create_user(
            email="student3@test.com",
            password=self.password,
            full_name="Bob Johnson",
            user_type="student",
        )

        self.test_class = Class.objects.create(
            name="Computer Science 101",
            description="Intro to CS",
            creator=self.lecturer,
            is_verified=True,
        )

        Membership.objects.create(user=self.lecturer, class_obj=self.test_class, role="lecturer")
        Membership.objects.create(user=self.student1, class_obj=self.test_class, role="student")
        Membership.objects.create(user=self.student2, class_obj=self.test_class, role="student")
        Membership.objects.create(user=self.student3, class_obj=self.test_class, role="student")

        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file_content",
            content_type="application/pdf",
        )

        self.upload = Upload.objects.create(
            file_name="test_document.pdf",
            file=test_file,
            file_size=len(b"file_content"),
            file_type="document",
            uploader=self.student1,
            class_obj=self.test_class,
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

    def test_share_file_success(self):
        self.authenticate(self.student1)

        response = self.client.post(
            "/api/v1/sharing/",
            {
                "file_code": self.upload.file_code,
                "shared_with_id": self.student2.id,
                "message": "Check out this document!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["status"], "pending")
        self.assertEqual(response.data["data"]["message"], "Check out this document!")
        self.assertTrue(
            SharedFile.objects.filter(upload=self.upload, shared_with=self.student2).exists()
        )

    def test_share_file_requires_owner(self):
        self.authenticate(self.student2)

        response = self.client.post(
            "/api/v1/sharing/",
            {
                "file_code": self.upload.file_code,
                "shared_with_id": self.student3.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data)

    def test_duplicate_share_is_rejected(self):
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            message="Existing share",
        )
        self.authenticate(self.student1)

        response = self.client.post(
            "/api/v1/sharing/",
            {
                "file_code": self.upload.file_code,
                "shared_with_id": self.student2.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data)

    @patch("apps.sharing.views.bulk_share_async")
    def test_bulk_share_returns_processing_response(self, bulk_share_async_mock):
        self.authenticate(self.student1)

        response = self.client.post(
            "/api/v1/sharing/bulk/",
            {
                "file_code": self.upload.file_code,
                "user_ids": [self.student2.id, self.student3.id],
                "message": "Sharing with multiple users",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["status"], "processing")
        self.assertEqual(response.data["data"]["user_count"], 2)
        bulk_share_async_mock.assert_called_once()

    def test_list_endpoints_return_expected_results(self):
        pending_share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status="pending",
            message="Pending request",
        )
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student3,
            status="accepted",
            message="Accepted request",
        )

        self.authenticate(self.student2)
        pending_response = self.client.get("/api/v1/sharing/requests/")
        shared_with_me_response = self.client.get("/api/v1/sharing/shared-with-me/")
        detail_response = self.client.get(f"/api/v1/sharing/{pending_share.id}/")

        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pending_response.data["count"], 1)
        self.assertEqual(pending_response.data["results"][0]["status"], "pending")

        self.assertEqual(shared_with_me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(shared_with_me_response.data["count"], 1)
        self.assertEqual(shared_with_me_response.data["results"][0]["file_code"], self.upload.file_code)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_response.data["success"])
        self.assertEqual(detail_response.data["data"]["id"], str(pending_share.id))

    def test_my_shares_lists_sent_shares(self):
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status="pending",
        )

        self.authenticate(self.student1)
        response = self.client.get("/api/v1/sharing/my-shares/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["shared_with_name"], self.student2.full_name)

    def test_accept_and_reject_share(self):
        accept_share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status="pending",
        )
        reject_share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student3,
            status="pending",
        )

        self.authenticate(self.student2)
        accept_response = self.client.post(f"/api/v1/sharing/{accept_share.id}/accept/")
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
        accept_share.refresh_from_db()
        self.assertEqual(accept_share.status, "accepted")
        self.assertIsNotNone(accept_share.accepted_at)

        self.authenticate(self.student3)
        reject_response = self.client.post(f"/api/v1/sharing/{reject_share.id}/reject/")
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        reject_share.refresh_from_db()
        self.assertEqual(reject_share.status, "rejected")
        self.assertIsNotNone(reject_share.rejected_at)

    def test_non_recipient_cannot_accept_share(self):
        share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status="pending",
        )

        self.authenticate(self.student3)
        response = self.client.post(f"/api/v1/sharing/{share.id}/accept/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_is_blocked(self):
        response = self.client.post(
            "/api/v1/sharing/",
            {
                "file_code": self.upload.file_code,
                "shared_with_id": self.student2.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SharingServiceTests(TestCase):
    def setUp(self):
        self.lecturer = User.objects.create_user(
            email="lecturer@service.com",
            password="test123",
            full_name="Dr. Service",
            user_type="lecturer",
        )
        self.student1 = User.objects.create_user(
            email="student1@service.com",
            password="test123",
            full_name="Service Student 1",
            user_type="student",
        )
        self.student2 = User.objects.create_user(
            email="student2@service.com",
            password="test123",
            full_name="Service Student 2",
            user_type="student",
        )

        self.test_class = Class.objects.create(
            name="Service Test Class",
            description="Testing",
            creator=self.lecturer,
            is_verified=True,
        )

        Membership.objects.create(user=self.lecturer, class_obj=self.test_class, role="lecturer")
        Membership.objects.create(user=self.student1, class_obj=self.test_class, role="student")
        Membership.objects.create(user=self.student2, class_obj=self.test_class, role="student")

        test_file = SimpleUploadedFile(
            "service_test.pdf",
            b"content",
            content_type="application/pdf",
        )

        self.upload = Upload.objects.create(
            file_name="service_test.pdf",
            file=test_file,
            file_size=7,
            file_type="document",
            uploader=self.student1,
            class_obj=self.test_class,
        )

    def test_can_share_file(self):
        self.assertTrue(SharingService.can_share_file(self.student1, self.upload))
        self.assertFalse(SharingService.can_share_file(self.student2, self.upload))

    def test_share_exists(self):
        self.assertFalse(SharingService.share_exists(self.upload, self.student2))

        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status="pending",
        )

        self.assertTrue(SharingService.share_exists(self.upload, self.student2))
