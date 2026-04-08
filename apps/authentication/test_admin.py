from django.test import TestCase
from django.urls import reverse

from apps.authentication.models import User


class AuthenticationAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            full_name="Admin User",
            password="adminpass123",
        )
        self.client.force_login(self.admin_user)

    def test_user_changelist_loads(self):
        response = self.client.get(reverse("admin:authentication_user_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin User")
