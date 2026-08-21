from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .client import KibegiAPI
from .config import get_settings
from .mcp_server import create_mcp

settings = get_settings()
client = KibegiAPI(settings)
mcp = create_mcp(settings, client)
app = FastAPI(title="Kibegi Agent Gateway", version="1.0.0")


class ProxyRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    user_token: str | None = None
    params: dict[str, Any] | None = None
    body: dict[str, Any] | list[Any] | None = None
    confirm: bool = False


def require_gateway_token(authorization: str | None) -> None:
    if not settings.go_api_service_token:
        return
    if authorization != f"Bearer {settings.go_api_service_token}":
        raise HTTPException(status_code=401, detail="Invalid gateway token")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"service": settings.app_name, "go_api": await client.health()}


@app.post("/v1/proxy")
async def proxy(request: ProxyRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_gateway_token(authorization)
    return await client.request(
        request.method,
        request.path,
        user_token=request.user_token,
        params=request.params,
        body=request.body,
        confirm=request.confirm,
    )


origins = [origin.strip() for origin in settings.mcp_allowed_origins.split(",") if origin.strip()]
mcp_app = mcp.http_app(
    path=settings.mcp_path,
    transport="http",
    stateless_http=True,
    json_response=True,
    allowed_origins=origins or None,
)
app.mount(settings.mcp_path, mcp_app)
