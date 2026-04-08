from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.classes.models import Class, Membership
from apps.storage.models import UserStorage
from apps.storage.services import StorageService
from apps.uploads.models import Upload

User = get_user_model()


class StorageServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="storage@test.com",
            password="test123",
            full_name="Storage User",
            user_type="student",
        )
        self.lecturer = User.objects.create_user(
            email="lecturer-storage@test.com",
            password="test123",
            full_name="Storage Lecturer",
            user_type="lecturer",
        )
        self.class_obj = Class.objects.create(
            name="Storage Class",
            description="Storage tests",
            creator=self.lecturer,
            is_verified=True,
        )
        Membership.objects.create(user=self.lecturer, class_obj=self.class_obj, role="lecturer")
        Membership.objects.create(user=self.user, class_obj=self.class_obj, role="student")

    def test_user_storage_created_for_new_user(self):
        storage = UserStorage.objects.get(user=self.user)

        self.assertEqual(float(storage.total_quota_mb), 50.0)
        self.assertEqual(storage.used_storage_bytes, 0)

    def test_storage_usage_recalculates_from_uploads(self):
        Upload.objects.create(
            file_name="first.pdf",
            file=SimpleUploadedFile("first.pdf", b"12345", content_type="application/pdf"),
            file_size=5,
            file_type="document",
            uploader=self.user,
            class_obj=self.class_obj,
        )
        Upload.objects.create(
            file_name="second.pdf",
            file=SimpleUploadedFile("second.pdf", b"1234567", content_type="application/pdf"),
            file_size=7,
            file_type="document",
            uploader=self.user,
            class_obj=self.class_obj,
        )

        storage = StorageService.update_user_storage(self.user)

        self.assertEqual(storage.used_storage_bytes, 12)
        self.assertGreaterEqual(storage.used_storage_mb, 0)
