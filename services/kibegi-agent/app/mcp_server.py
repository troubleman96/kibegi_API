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

    return mcp
