"""
Integration tests for friends list behavior.

Run with:
    venv/bin/python manage.py test apps.friends --settings=kibegi_api.test_settings
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.friends.models import Friendship


User = get_user_model()


class FriendListDedupTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.password = "test123"

        self.user_a = User.objects.create_user(
            email="a@test.com",
            password=self.password,
            full_name="User A",
            user_type="student",
        )
        self.user_b = User.objects.create_user(
            email="b@test.com",
            password=self.password,
            full_name="User B",
            user_type="student",
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

    def test_accepted_list_dedupes_reverse_friendships_and_never_shows_self_name(self):
        # Two directional accepted rows can exist when nicknames are set by both sides.
        Friendship.objects.create(user=self.user_a, friend=self.user_b, status="accepted")
        Friendship.objects.create(user=self.user_b, friend=self.user_a, status="accepted", nickname="Bestie")

        self.authenticate(self.user_b)
        response = self.client.get("/api/v1/friends/?status=accepted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        # Must show only one entry for the other user.
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["friend_info"]["email"], self.user_a.email)
        self.assertEqual(item["nickname"], "Bestie")
        self.assertEqual(item["display_name"], "Bestie")

        # Ensure it doesn't mistakenly show the current user's own name.
        self.assertNotEqual(item["display_name"], self.user_b.full_name)

    def test_accepted_list_without_reverse_row_shows_other_user_name(self):
        Friendship.objects.create(user=self.user_a, friend=self.user_b, status="accepted")

        self.authenticate(self.user_b)
        response = self.client.get("/api/v1/friends/?status=accepted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["friend_info"]["email"], self.user_a.email)
        self.assertEqual(item["nickname"], "")
        self.assertEqual(item["display_name"], self.user_a.full_name)
