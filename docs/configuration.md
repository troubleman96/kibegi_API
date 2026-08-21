# Kibegi Configuration Reference

## Configuration model

All services read environment variables. The committed `.env.example` is a placeholder template and must not be used as a production secret store. Use a deployment secret manager, protected systemd environment file, or container secret mechanism. Restart the affected service after changing configuration; most values are loaded at process startup.

## Go API variables

| Variable | Purpose | Notes |
|---|---|---|
| `HTTP_ADDR` | Listen address, usually `:8080`. | Bind privately when a reverse proxy is used. |
| `SECRET_KEY` | JWT signing/validation secret. | Must be stable across restarts and rotated deliberately. |
| `ACCESS_TOKEN_LIFETIME` | Access-token duration. | Preserve client expectations when changing. |
| `REFRESH_TOKEN_LIFETIME` | Refresh-token duration. | Revocation uses Redis when configured. |
| `DATABASE_URL` | PostgreSQL connection string. | Points at the existing Kibegi schema. |
| `DB_MAX_OPEN_CONNS` / `DB_MAX_IDLE_CONNS` | Pool bounds. | Tune against PostgreSQL capacity. |
| `DB_CONN_MAX_LIFETIME` / `DB_CONN_MAX_IDLE_TIME` | Pool recycling. | Prevent stale connections. |
| `REDIS_URL` | Redis connection URL. | Enables caches, locks, counters, rate limiting, and revocations. |
| `REDIS_POOL_SIZE` / `REDIS_MIN_IDLE_CONNS` | Redis pool settings. | Tune for concurrent traffic. |
| `MINIO_ENABLED` | Enables object storage. | Must be true with a complete storage configuration. |
| `MINIO_ENDPOINT` | MinIO/S3 endpoint. | May include `http://` or `https://`. |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Object-storage credentials. | Use least privilege. |
| `MINIO_BUCKET` | Object bucket. | Must contain existing upload objects. |
| `MINIO_SECURE` / `MINIO_PUBLIC_BASE_URL` | Transport and public URL behavior. | Keep public URL separate from private endpoint. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Email provider. | Used by OTP and approval flows. |
| `SENDAFRICA_API_KEY`, `SENDAFRICA_BASE_URL`, `SENDAFRICA_SENDER_ID` | SMS provider. | Used by SMS accounts, broadcasts, and reminders. |
| `KIBEGI_CORS_ORIGIN` | Allowed browser origin. | Use a specific production frontend origin. |
| `AI_INDEXER_URL` | Private indexer base URL. | Go calls `/v1/index/uploads/{upload_id}` after uploads. |
| `AI_INDEXER_TOKEN` | Private callback bearer token. | Must match indexer `SERVICE_TOKEN`. |

## FastAPI AI indexer variables

The indexer requires `DATABASE_URL`, MinIO variables, and optionally `REDIS_URL`. `SERVICE_TOKEN` protects indexing endpoints. `JOB_STALE_MINUTES`, `DEFAULT_BATCH_LIMIT`, `MAX_DOWNLOAD_BYTES`, `CHUNK_SIZE`, and `CHUNK_OVERLAP` control job behavior. `NGAMIA_BASE_URL`, `NGAMIA_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE`, and `EMBEDDING_TIMEOUT_SECONDS` control optional embedding generation.

If `NGAMIA_API_KEY` is absent or an embedding batch fails, chunks are still persisted with zero vectors. If PostgreSQL or MinIO is absent, health reports degraded and indexing endpoints return `503` rather than silently claiming success.

## FastAPI/FastMCP gateway variables

`GO_API_BASE_URL` identifies the Go API. `GO_API_SERVICE_TOKEN` optionally protects the gateway’s REST proxy; it is separate from user JWTs. `REQUEST_TIMEOUT_SECONDS` bounds outgoing Go calls. `MCP_PATH` controls the mounted FastMCP route, normally `/mcp`. `MCP_ALLOWED_ORIGINS` is a comma-separated origin allowlist for MCP HTTP transport.

## Environment validation

After changing configuration, perform a health check for each process, an authenticated API request, an indexer service-token test, an MCP connection test, and a representative object-storage operation. Never validate by printing the complete environment. Redact tokens and credentials in shell output.
