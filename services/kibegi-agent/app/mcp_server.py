from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from .client import KibegiAPI
from .config import Settings


def create_mcp(settings: Settings, client: KibegiAPI) -> FastMCP:
    mcp = FastMCP(
        name="kibegi-agent",
        version="1.0.0",
        instructions="Use these tools to access the authenticated Kibegi Go API. Mutations require explicit confirm=true.",
    )

    @mcp.tool
    async def health() -> dict[str, Any]:
        """Check Kibegi Go API health and dependency readiness."""
        return await client.health()

    @mcp.tool
    async def api_request(
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        path: str,
        user_token: str | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Call any allowlisted `/api/v1/` Kibegi route; non-GET calls require confirm=true."""
        return await client.request(method, path, user_token=user_token, params=params, body=body, confirm=confirm)

    @mcp.tool
    async def search_kibegi(query: str, user_token: str) -> dict[str, Any]:
        """Search users, classes, files, friends, and library records for the authenticated user."""
        return await client.search(query, user_token)

    @mcp.tool
    async def list_classes(user_token: str, query: str | None = None) -> dict[str, Any]:
        """List classes visible to the authenticated user."""
        return await client.list_classes(user_token, query)

    @mcp.tool
    async def list_uploads(user_token: str, query: str | None = None) -> dict[str, Any]:
        """List accessible uploads for the authenticated user."""
        return await client.list_uploads(user_token, query)

    @mcp.tool
    async def get_storage(user_token: str) -> dict[str, Any]:
        """Read the authenticated user's storage quota and usage."""
        return await client.get_storage(user_token)

    @mcp.tool
    async def get_schedule(user_token: str) -> dict[str, Any]:
        """Read the authenticated user's schedule calendars."""
        return await client.get_schedule(user_token)

    @mcp.tool
    async def get_ai_status(upload_id: str, user_token: str) -> dict[str, Any]:
        """Read AI indexing status for an upload."""
        return await client.get_ai_status(upload_id, user_token)

    @mcp.tool
    async def list_notifications(user_token: str) -> dict[str, Any]:
        """List notifications for the authenticated user."""
        return await client.list_notifications(user_token)

    @mcp.tool
    async def list_friends(user_token: str) -> dict[str, Any]:
        """List friendships and friend requests for the authenticated user."""
        return await client.list_friends(user_token)

    @mcp.tool
    async def list_shares(user_token: str) -> dict[str, Any]:
        """List file shares for the authenticated user."""
        return await client.list_shares(user_token)

    @mcp.tool
    async def list_marketplace(user_token: str) -> dict[str, Any]:
        """List marketplace listings visible to the authenticated user."""
        return await client.list_marketplace(user_token)

    @mcp.tool
    async def list_library(user_token: str) -> dict[str, Any]:
        """List library items visible to the authenticated user."""
        return await client.list_library(user_token)

    @mcp.tool
    async def list_channels(user_token: str) -> dict[str, Any]:
        """List channels visible to the authenticated user."""
        return await client.list_channels(user_token)

    @mcp.tool
    async def list_class_comms(class_id: str, user_token: str) -> dict[str, Any]:
        """List class communications contacts for a class."""
        return await client.list_class_comms(class_id, user_token)

    @mcp.tool
    async def list_assignments(class_id: str, user_token: str) -> dict[str, Any]:
        """List assignments for a class."""
        return await client.list_assignments(class_id, user_token)

    @mcp.tool
    async def list_sms_deliveries(user_token: str) -> dict[str, Any]:
        """List SMS delivery history for the authenticated user."""
        return await client.list_sms_deliveries(user_token)

    @mcp.tool
    async def upload_file(file_name: str, content_base64: str, class_id: str, user_token: str, confirm: bool = False) -> dict[str, Any]:
        """Upload a file through Go; requires confirm=true and base64 content."""
        return await client.upload_file(file_name, content_base64, class_id, user_token, confirm)

    @mcp.tool
    async def download_file(file_code: str, user_token: str) -> dict[str, Any]:
        """Download an accessible upload as base64 content."""
        return await client.download_file(file_code, user_token)

    return mcp
