from __future__ import annotations

from typing import Any, Literal

import httpx

from .config import Settings


ALLOWED_PREFIXES = (
    "/api/v1/health/",
    "/api/v1/auth/",
    "/api/v1/classes/",
    "/api/v1/uploads/",
    "/api/v1/files/",
    "/api/v1/storage/",
    "/api/v1/sharing/",
    "/api/v1/notifications/",
    "/api/v1/friends/",
    "/api/v1/schedule/",
    "/api/v1/public/schedule/",
    "/api/v1/marketplace/",
    "/api/v1/library/",
    "/api/v1/channel/",
    "/api/v1/public/channel/",
    "/api/v1/class-comms/",
    "/api/v1/public/class-comms/",
    "/api/v1/assignments/",
    "/api/v1/ai/",
    "/api/v1/search/",
    "/api/v1/sms/",
)


class KibegiAPI:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        if not path.startswith(ALLOWED_PREFIXES):
            raise ValueError("Path is outside the exposed Kibegi API namespace")
        return self.settings.go_api_base_url.rstrip("/") + path

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        path: str,
        *,
        user_token: str | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if method != "GET" and not confirm:
            raise ValueError("Mutation requires confirm=true")
        headers = {"Accept": "application/json"}
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        if self.settings.go_api_service_token:
            headers["X-Service-Token"] = self.settings.go_api_service_token
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.request(method, self._url(path), headers=headers, params=params, json=body)
            try:
                payload = response.json()
            except ValueError:
                payload = {"success": response.is_success, "message": response.text, "data": None, "errors": None}
            if response.is_error:
                return {"http_status": response.status_code, "response": payload}
            return {"http_status": response.status_code, "response": payload}

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/health/")

    async def search(self, query: str, user_token: str) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/search/", user_token=user_token, params={"q": query})

    async def list_classes(self, user_token: str, query: str | None = None) -> dict[str, Any]:
        params = {"search": query} if query else None
        return await self.request("GET", "/api/v1/classes/", user_token=user_token, params=params)

    async def list_uploads(self, user_token: str, query: str | None = None) -> dict[str, Any]:
        params = {"search": query} if query else None
        return await self.request("GET", "/api/v1/uploads/", user_token=user_token, params=params)

    async def get_schedule(self, user_token: str) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/schedule/calendars/", user_token=user_token)

    async def get_ai_status(self, upload_id: str, user_token: str) -> dict[str, Any]:
        return await self.request("GET", f"/api/v1/ai/status/{upload_id}/", user_token=user_token)

    async def get_storage(self, user_token: str) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/storage/", user_token=user_token)
