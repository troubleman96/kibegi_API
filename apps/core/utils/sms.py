"""Shared SMS provider helpers used by schedule and class communications.

The project currently sends SMS through Africa's Talking. Keeping the adapter in
one small utility makes it easier to reuse the same provider rules across apps
without copying the HTTP code or response parsing in multiple places.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class AfricasTalkingSmsClient:
    """Small adapter around the Africa's Talking SMS API."""

    def __init__(self):
        self.username = getattr(settings, "AFRICASTALKING_USERNAME", "")
        self.api_key = getattr(settings, "AFRICASTALKING_API_KEY", "")
        self.sender_id = getattr(settings, "AFRICASTALKING_SENDER_ID", "")
        self.messaging_url = getattr(
            settings,
            "AFRICASTALKING_SMS_URL",
            "https://api.africastalking.com/version1/messaging",
        )

    def is_configured(self):
        """Return True when the provider credentials are available."""
        return bool(self.username and self.api_key)

    def send_sms(self, phone_number: str, message: str, sender_id: str = ""):
        """Send a single SMS message and return the provider response payload."""
        if not self.is_configured():
            raise RuntimeError("Africa's Talking SMS settings are not configured.")

        payload = {
            "username": self.username,
            "to": phone_number,
            "message": message,
        }
        active_sender = sender_id or self.sender_id
        if active_sender:
            payload["from"] = active_sender

        encoded_payload = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(self.messaging_url, data=encoded_payload, method="POST")
        request.add_header("apiKey", self.api_key)
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise RuntimeError(f"Africa's Talking SMS request failed: {exc.code} {error_body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Africa's Talking SMS request failed: {exc.reason}") from exc

        try:
            response_data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Africa's Talking SMS returned invalid JSON.") from exc

        recipients = response_data.get("SMSMessageData", {}).get("Recipients", [])
        recipient = recipients[0] if recipients else {}
        return {
            "provider_message_id": recipient.get("messageId", ""),
            "raw_response": response_data,
        }
