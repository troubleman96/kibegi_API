from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Class, Membership

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver"])
class ClassQRCodeAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="classmate@test.com",
            password="StrongPass123!",
            full_name="Class Mate",
            user_type="student",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.class_obj = Class.objects.create(
            name="Mathematics",
            description="Intro to algebra",
            creator=self.user,
            is_public=True,
            is_verified=False,
        )
        Membership.objects.create(user=self.user, class_obj=self.class_obj, role="student")

    def test_class_detail_includes_scan_to_join_qr(self):
        response = self.client.get(reverse("classes:detail", kwargs={"pk": self.class_obj.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        payload = response.data["data"]
        self.assertEqual(payload["join_qr_payload"]["type"], "class_join")
        self.assertEqual(payload["join_qr_payload"]["class_code"], self.class_obj.class_code)
        self.assertEqual(payload["join_qr_payload"]["join_endpoint"], "/api/v1/classes/join/")
        self.assertEqual(payload["join_qr_value"], self.class_obj.class_code)
        self.assertTrue(payload["join_qr_image"].startswith("data:image/png;base64,"))
