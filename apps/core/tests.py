import json

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.core.models import RequestLog
from kibegi_api.middleware import RequestLoggingMiddleware


class RequestLoggingMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestLoggingMiddleware(lambda request: HttpResponse("ok"))

    def test_process_response_logs_api_request_body(self):
        request = self.factory.post(
            "/api/v1/test/",
            data=json.dumps({"email": "user@example.com", "password": "secret123"}),
            content_type="application/json",
        )
        request.user = AnonymousUser()

        self.middleware.process_request(request)
        response = HttpResponse(status=201)
        self.middleware.process_response(request, response)

        log = RequestLog.objects.get()
        self.assertEqual(log.path, "/api/v1/test/")
        self.assertEqual(log.status_code, 201)
        self.assertEqual(log.request_body["email"], "user@example.com")
        self.assertEqual(log.request_body["password"], "*****")

    def test_process_exception_logs_server_error(self):
        request = self.factory.get("/api/v1/failing/?page=1")
        request.user = AnonymousUser()

        self.middleware.process_request(request)
        self.middleware.process_exception(request, RuntimeError("boom"))

        log = RequestLog.objects.get()
        self.assertEqual(log.status_code, 500)
        self.assertIn("boom", log.error_message)
        self.assertEqual(log.request_body["page"], "1")
