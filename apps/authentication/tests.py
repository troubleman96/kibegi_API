"""
Tests for the authentication app.

Run with:
    venv/bin/python manage.py test apps.authentication --settings=kibegi_api.test_settings
"""

import base64
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient


User = get_user_model()


class ProfileImageUrlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "test123"

        self.user = User.objects.create_user(
            email="user@test.com",
            password=self.password,
            full_name="Test User",
            user_type="student",
        )

        # 1x1 transparent PNG
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6X9k3kAAAAASUVORK5CYII="
        )
        self.user.profile_image = SimpleUploadedFile(
            "avatar.png",
            png_bytes,
            content_type="image/png",
        )
        self.user.save()

    def test_login_returns_absolute_profile_image_url(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        profile_image_url = response.data["data"]["user"]["profile_image_url"]
        self.assertIsNotNone(profile_image_url)
        self.assertTrue(
            profile_image_url.startswith(("http://", "https://")),
            msg=f"Expected absolute URL, got: {profile_image_url}",
        )
        self.assertNotIn(
            "/api/v1/",
            profile_image_url,
            msg=f"URL should not be joined against API path: {profile_image_url}",
        )


class GoogleLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("urllib.request.urlopen")
    def test_google_login_accepts_access_token(self, mock_urlopen):
        mock_response = {
            "email": "google-user@test.com",
            "email_verified": True,
            "name": "Google User",
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        response = self.client.post(
            "/api/v1/auth/google/",
            {"access_token": "access-token-value"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["user"]["email"], "google-user@test.com")
        self.assertIn("access", response.data["data"]["tokens"])
        self.assertIn("refresh", response.data["data"]["tokens"])

    @override_settings(GOOGLE_CLIENT_ID="client-id")
    @patch("urllib.request.urlopen")
    def test_google_login_accepts_credential_token(self, mock_urlopen):
        mock_response = {
            "email": "credential-user@test.com",
            "email_verified": True,
            "name": "Credential User",
            "aud": "client-id",
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()

        response = self.client.post(
            "/api/v1/auth/google/",
            {"credential": "credential-token-value"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["user"]["email"], "credential-user@test.com")
