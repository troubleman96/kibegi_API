from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class HealthCheckAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "healthy")
        self.assertEqual(response.data["data"]["status"], "ok")
        self.assertEqual(response.data["data"]["service"], "kibegi_api")
        self.assertEqual(response.data["data"]["checks"]["database"]["status"], "ok")
