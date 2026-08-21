# Kibegi API Contract

## Base URL and path rules

The primary API is served by the Go process under `/api/v1/`. Routes preserve trailing slashes because existing clients rely on them. The root compatibility shortcuts `/register/` and `/login/` remain available for clients that have not yet moved to `/api/v1/auth/`.

The public route families are `/api/v1/public/schedule/`, `/api/v1/public/channel/`, and `/api/v1/public/class-comms/`. The class communications implementation also accepts `/api/v1/classcomms/` as a compatibility alias for `/api/v1/class-comms/`.

## Standard JSON envelope

Most JSON responses use the following structure:

```json
{
  "success": true,
  "message": "Resources retrieved successfully",
  "data": {},
  "errors": null
}
```

`data` may be an object, array, page object, or null. `errors` may be null, an object, or a validation collection. Clients should inspect HTTP status and `success` together. The health endpoint intentionally preserves the existing unhealthy behavior in which the envelope can contain `success: true` while the HTTP status is `503` and `data.status` is `error`.

## Authentication

Protected routes accept a Django SimpleJWT-compatible access token in `Authorization: Bearer <access-token>`. Access tokens and refresh tokens use the configured Go token service and preserve the existing claim names and identifier formats. Refresh, logout, and password-change flows remain under authentication routes. Public schedule, channel, and class-comms information routes do not require a user token.

The agent gateway accepts an end-user JWT as a tool argument and forwards it unchanged to Go. The gateway’s own `GO_API_SERVICE_TOKEN`, when configured, protects the gateway transport; it is not a replacement for the end-user JWT used by Go domain authorization.

## Status conventions

| Status | Meaning |
|---:|---|
| `200` | Successful read, update, transition, or deletion response. |
| `201` | Successful creation, registration, upload, share, purchase, or join. |
| `204` | CORS preflight response with no body. |
| `400` | Malformed JSON, invalid input, unsupported transition, or provider request rejected by validation. |
| `401` | Missing, malformed, expired, or invalid authentication. |
| `403` | Authenticated user lacks ownership, membership, role, or permission. |
| `404` | Resource or compatibility route does not exist. |
| `405` | HTTP method is not implemented for an existing route. |
| `409` | Duplicate or conflicting state where the domain returns a conflict. |
| `429` | Redis-backed client rate limit exceeded. |
| `500` | Unexpected internal failure or recovered panic. |
| `503` | Database, Redis readiness, storage, or provider dependency unavailable. |

## Pagination

List endpoints generally accept `page`, `limit`, and `offset` conventions according to their domain handler. Paginated responses use a page object with `count`, `next`, `previous`, and `results`. The `next` and `previous` values are generated from the active request URL and preserve query parameters when possible. Clients should treat `results` as the collection and not assume that every list endpoint is paginated in exactly the same way.

## Uploads and files

Native upload routes are under `/api/v1/uploads/`; the legacy unified-file compatibility surface is under `/api/v1/files/`. Uploads use multipart form data with a `file` part and a `class_obj` UUID. The Go API enforces a 50MB maximum, stores objects under the existing `uploads/<user-id>/<filename>` convention, and starts asynchronous AI indexing after the upload row is committed.

File downloads are streaming responses rather than JSON envelopes. The FastMCP gateway converts download bytes to base64 so an MCP client can transport them as structured data. File deletion is soft deletion first; permanent deletion is a separate operation and removes the object after the database authorization check.

## Route families

| Prefix | Domain |
|---|---|
| `/api/v1/health/` | Readiness. |
| `/api/v1/auth/` | Authentication and profiles. |
| `/api/v1/classes/` | Classes and memberships. |
| `/api/v1/uploads/` | Upload lifecycle. |
| `/api/v1/files/` | Unified file compatibility. |
| `/api/v1/storage/` | User quota and usage. |
| `/api/v1/sharing/` | Shares and share requests. |
| `/api/v1/notifications/` | Notification state. |
| `/api/v1/friends/` | Friendship lifecycle. |
| `/api/v1/schedule/` | Private schedules. |
| `/api/v1/public/schedule/` | Public schedule feeds. |
| `/api/v1/marketplace/` | Marketplace. |
| `/api/v1/library/` | Library. |
| `/api/v1/channel/` | Channels. |
| `/api/v1/public/channel/` | Public channel information and join. |
| `/api/v1/class-comms/` | Class communications. |
| `/api/v1/public/class-comms/` | Public class registration. |
| `/api/v1/assignments/` | Assignments and submissions. |
| `/api/v1/ai/` | AI configuration, conversations, usage, messages, and processing status. |
| `/api/v1/search/` | Global search and history. |
| `/api/v1/sms/` | SMS accounts, top-ups, and delivery history. |

## Compatibility requirements for changes

A route change must preserve the path, slash behavior, method, envelope keys, identifier format, authorization decision, and meaningful status code unless the client contract is intentionally versioned. Add or update a Go handler test for method, validation, authorization, and not-found behavior. Add a gateway tool or update `services/kibegi-agent/API_TOOL_COVERAGE.md` when an API family changes.
