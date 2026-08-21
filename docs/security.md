# Kibegi Security Guide

## Trust boundaries

The public trust boundary ends at the Go API and the separately protected agent gateway. The AI indexer, PostgreSQL, Redis, and MinIO/S3 should remain on a private network. The indexer token is a server-to-server credential and must never be embedded in frontend code or MCP tool descriptions. The agent gateway receives user tokens only for the duration of a request and must not persist them.

## Authentication and authorization

The Go authentication package validates Django SimpleJWT-compatible access and refresh tokens, preserves configured lifetimes, and uses the existing integer user ID in the request context. Passwords are verified with PBKDF2-SHA256 compatibility logic. Protected handlers must obtain the authenticated user ID from context and enforce domain ownership, membership, role, and approval rules before reading or mutating records.

Do not implement authorization solely in the FastMCP gateway. The gateway forwards the user JWT, but Go remains responsible for the final authorization decision. Public routes must be intentionally registered under their public prefixes and must not accidentally expose private repository queries.

## Service credentials

| Credential | Used by | Storage rule |
|---|---|---|
| `SECRET_KEY` | Go JWT signing/validation | Long random secret in a deployment secret manager. |
| `AI_INDEXER_TOKEN` | Go-to-indexer callback | Private server secret; rotate independently from user JWT signing. |
| `GO_API_SERVICE_TOKEN` | Optional agent gateway transport protection | Private gateway secret; never return it from `/health`. |
| `DATABASE_URL` | Go and indexer PostgreSQL access | Secret manager or protected environment. |
| MinIO access/secret keys | Go and indexer object access | Least-privilege bucket credentials. |
| SMTP credentials | Go email provider | Secret manager; never log message credentials. |
| SendAfrica credentials | Go SMS provider | Secret manager; redact provider responses in logs. |
| Ngamia/OpenAI-compatible key | Go AI and indexer embeddings | Secret manager; do not return unmasked keys. |

`.env.example` contains placeholders only. Do not commit `.env`, access keys, bearer tokens, uploaded cookie files, or provider response dumps.

## HTTP controls

The Go middleware adds request IDs, structured access logs, panic recovery, request timeouts, CORS headers, and Redis-backed client rate limiting. Set `KIBEGI_CORS_ORIGIN` to the deployed frontend origin; do not rely on the wildcard outside development. Place the service behind a TLS reverse proxy and configure trusted proxy headers carefully. Request IDs should be included in operational logs and support tickets.

The rate limiter is intentionally fail-open when Redis is unavailable so a cache outage does not take down the API. Operations that require atomic coordination use repository transactions or explicit Redis locks and must not silently downgrade if doing so could duplicate a purchase, spend credits twice, or create inconsistent membership state.

## File and upload security

Uploads are size-limited, stored under controlled object names, and accessed only after database authorization. Never construct an object key from an untrusted path without applying `filepath.Base` or an equivalent safe-name operation. Do not expose MinIO credentials or internal object endpoints in API payloads. Download responses must preserve content type and disposition without reflecting arbitrary header values.

The agent’s base64 upload tool enforces the Go API’s 50MB limit and requires explicit confirmation. The FastMCP generic tool is path-allowlisted; it cannot call arbitrary administrative or filesystem endpoints. Mutation calls require `confirm=true`.

## Logging and privacy

Logs may include request IDs, method, route, status, duration, and safe error categories. Do not log passwords, JWTs, SMTP credentials, SMS API keys, MinIO keys, raw uploaded document text, embeddings, or full provider payloads. AI indexing errors should contain upload IDs and bounded diagnostic messages, not document contents.

## Security review checklist

Before production deployment, verify TLS, secret injection, private service networking, PostgreSQL least privilege, Redis authentication, MinIO bucket policy, CORS origin, proxy header configuration, rate-limit behavior, token rotation, backup encryption, log redaction, MCP authentication, and audit logging. Re-run unauthorized and cross-user access tests for every new handler and every new MCP mutation tool.
