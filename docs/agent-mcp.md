# FastAPI Agent and FastMCP Gateway

## Purpose

`services/kibegi-agent` exposes the Go-primary Kibegi API to Python agents and MCP clients. It is a protocol and policy layer, not a replacement domain backend. It forwards requests to Go, preserves Go response envelopes, and keeps authorization in the Go service.

## Components

| File | Responsibility |
|---|---|
| `app/config.py` | Gateway base URL, token, timeout, path, and origin settings. |
| `app/client.py` | Async HTTP client, path allowlist, mutation confirmation, JSON proxy, multipart upload, and binary download. |
| `app/mcp_server.py` | FastMCP instance and typed tool registration. |
| `app/main.py` | FastAPI health/proxy endpoints and FastMCP HTTP mounting. |
| `tests/test_client.py` | Path and mutation-safety tests. |
| `API_TOOL_COVERAGE.md` | Complete namespace-to-tool map. |

## Tool categories

Typed tools cover common read workflows:

| Tool | Purpose |
|---|---|
| `health` | Check the Go API. |
| `search_kibegi` | Search users, classes, files, friends, and library records. |
| `list_classes` | List visible classes. |
| `list_uploads` | List accessible uploads. |
| `upload_file` / `download_file` | Transfer files through the Go API. |
| `get_storage` | Read quota and usage. |
| `list_shares` | Read file shares. |
| `list_notifications` | Read notifications. |
| `list_friends` | Read friendships and requests. |
| `get_schedule` | Read calendars. |
| `list_marketplace` | Read marketplace listings. |
| `list_library` | Read library items. |
| `list_channels` | Read channels. |
| `list_class_comms` | Read class communication contacts. |
| `list_assignments` | Read assignments for a class. |
| `get_ai_status` | Read upload indexing status from Go. |
| `list_sms_deliveries` | Read SMS delivery history. |

The generic `api_request` tool completes coverage for all allowlisted prefixes. It accepts an HTTP method, path, query parameters, JSON body, end-user JWT, and explicit confirmation flag. This covers authentication, public schedule/channel/class-comms routes, detail routes, transitions, purchases, joins, profile changes, storage recalculation, and deletions without requiring a separate tool wrapper for every UUID-shaped route.

## Safety model

The gateway enforces four controls before forwarding a request:

1. The path must begin with one of the migrated Kibegi API prefixes.
2. The method must be one of the explicit supported methods.
3. Every non-GET request must include `confirm=true`.
4. The caller’s end-user JWT is forwarded to Go, where the final authorization decision is made.

The gateway’s optional `GO_API_SERVICE_TOKEN` protects its own REST proxy endpoint. It does not grant domain access and must not be confused with a user access token. Production deployments should place `/mcp` behind TLS, an authenticated ingress, origin restrictions, request-size limits, and audit logging.

## File transport

MCP clients that cannot receive raw HTTP streams can use `upload_file` with base64 content and `download_file`, which returns base64 content. Uploads are limited to the Go API’s 50MB limit. Base64 increases transport size, so clients should prefer direct upload/download integrations for large files when available.

## FastAPI routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Reports gateway and upstream Go health. |
| `POST` | `/v1/proxy` | Protected JSON proxy for allowlisted Go paths. |
| MCP transport | `/mcp` | FastMCP HTTP transport. |

## Authentication flow

A trusted client authenticates to the gateway transport with the gateway’s deployment-level mechanism. Each tool call supplies the Kibegi user’s access token when the downstream route is protected. The gateway forwards `Authorization: Bearer <user-token>` to Go. Go validates expiration, signature, user ID, membership, ownership, and role. The gateway does not issue, refresh, blacklist, or persist Go tokens.

## Adding a new tool

When adding a Go route, first register and test the Go handler. Then add a typed client method if the operation is common or data-rich, register an MCP function with a descriptive docstring, update `API_TOOL_COVERAGE.md`, add a safety test for mutation behavior, and run the full Go/Python verification commands. Preserve the generic allowlist only when the route is intentionally available to agents.
