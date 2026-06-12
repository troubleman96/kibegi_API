"""Shared SMS provider helpers.

SendAfrica (sendafrica.online) is the primary provider.
AfricasTalkingSmsClient is kept for backward compatibility with existing tests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class SendAfricaSmsClient:
    """Adapter for the SendAfrica SMS API (sendafrica.online)."""

    BASE_URL = "https://sendafrica.online"

    def __init__(self):
        self.api_key = getattr(settings, "SENDAFRICA_API_KEY", "")
        self.sender_id = getattr(settings, "SENDAFRICA_SENDER_ID", "Kibegi")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def send_sms(self, phone_number: str, message: str, sender_id: str = "") -> dict:
        if not self.is_configured():
            raise RuntimeError("SENDAFRICA_API_KEY is not configured.")

        payload: dict = {"to": phone_number, "message": message}
        active_sender = sender_id or self.sender_id
        if active_sender:
            payload["from"] = active_sender

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.BASE_URL}/v1/sms/",
            data=body,
            method="POST",
        )
        req.add_header("X-API-Key", self.api_key)
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise RuntimeError(f"SendAfrica SMS failed: {exc.code} {error_body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SendAfrica SMS connection error: {exc.reason}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SendAfrica returned invalid JSON.") from exc

        if not data.get("success"):
            err = data.get("error", {})
            raise RuntimeError(f"[{err.get('code', 'error')}] {err.get('message', 'Unknown error')}")

        result = data.get("data", {})
        return {
            "provider_message_id": result.get("message_id", ""),
            "raw_response": data,
        }


class AfricasTalkingSmsClient:
    """Legacy Africa's Talking adapter — kept for existing test patches."""

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
        return bool(self.username and self.api_key)

    def send_sms(self, phone_number: str, message: str, sender_id: str = ""):
        if not self.is_configured():
            raise RuntimeError("Africa's Talking SMS settings are not configured.")

        payload = {"username": self.username, "to": phone_number, "message": message}
        active_sender = sender_id or self.sender_id
        if active_sender:
            payload["from"] = active_sender

        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(self.messaging_url, data=encoded, method="POST")
        req.add_header("apiKey", self.api_key)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            raise RuntimeError(f"Africa's Talking SMS failed: {exc.code} {error_body or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Africa's Talking SMS error: {exc.reason}") from exc

        try:
            response_data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Africa's Talking returned invalid JSON.") from exc

        recipients = response_data.get("SMSMessageData", {}).get("Recipients", [])
        recipient = recipients[0] if recipients else {}
        return {
            "provider_message_id": recipient.get("messageId", ""),
            "raw_response": response_data,
        }
