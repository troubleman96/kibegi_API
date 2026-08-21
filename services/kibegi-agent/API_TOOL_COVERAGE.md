# Kibegi Agent and FastMCP Tool Coverage

The gateway exposes the migrated Go API through two layers. Typed tools provide common operations with descriptive schemas, while `api_request` provides complete coverage for every allowlisted route, including less-frequently used detail and mutation paths.

| API namespace | Typed tools | Complete fallback |
|---|---|---|
| Health | `health` | `api_request(GET, /api/v1/health/)` |
| Authentication | End-user JWT passed to every tool; login/profile/OTP/password-reset calls available through proxy | `api_request` |
| Classes | `list_classes` | `api_request` |
| Uploads and files | `list_uploads`, `upload_file`, `download_file` | `api_request` |
| Storage | `get_storage` | `api_request` |
| Sharing | `list_shares` | `api_request` |
| Notifications | `list_notifications` | `api_request` |
| Friends | `list_friends` | `api_request` |
| Schedule | `get_schedule` | `api_request` |
| Marketplace | `list_marketplace` | `api_request` |
| Library | `list_library` | `api_request` |
| Channel | `list_channels` | `api_request` |
| Class communications | `list_class_comms` | `api_request` |
| Assignments | `list_assignments` | `api_request` |
| AI | `get_ai_status` | `api_request` |
| Search | `search_kibegi` | `api_request` |
| SMS | `list_sms_deliveries` | `api_request` |
| Public schedule, channel, and class-comms routes | Public paths are allowed by the proxy | `api_request` |

## Safety controls

The proxy rejects paths outside the migrated `/api/v1/` prefixes. Every non-GET call requires `confirm=true`, including file uploads, purchases, joins, profile changes, and deletions. End-user JWTs are passed explicitly and are never stored by the gateway. File upload accepts base64 data and enforces the Go service’s 50MB upload limit; file download returns base64 content for MCP clients that cannot receive raw HTTP streams.

The gateway’s own HTTP proxy can be protected with `GO_API_SERVICE_TOKEN`. Production deployments should additionally place the FastMCP endpoint behind TLS, authentication, origin restrictions, request-size limits, and audit logging.
