# Kibegi Operations Runbook

## Services

A normal deployment runs the Go API, the FastAPI AI indexer, and the FastAPI/FastMCP gateway as independent supervised processes. PostgreSQL, Redis, and MinIO/S3 are dependencies and should normally be managed services or separately supervised infrastructure.

| Process | Default port | Readiness endpoint |
|---|---:|---|
| Go API | `8080` | `GET /api/v1/health/` |
| AI indexer | `8090` | `GET /health` |
| Agent gateway | `8091` | `GET /health` |

## Startup order

Start PostgreSQL, Redis, and MinIO/S3 first. Start the Go API next and confirm that its health endpoint reports the expected dependency states. Start the AI indexer after database and object storage are reachable. Start the agent gateway after the Go API is reachable. A reverse proxy should only route traffic to a service after its process is listening and its health check is passing.

## Health interpretation

The Go health endpoint checks database and Redis readiness and can return `503` when the database is missing or unavailable. The JSON envelope remains available for diagnostics. The indexer health response reports database, storage, and Redis configuration/readiness. The agent health response includes the upstream Go health result. A degraded support service should not be mistaken for a healthy indexing or gateway path.

## Logs

The Go access logger records request ID, method, path, status, bytes, and duration. Use the request ID to correlate frontend reports with service logs. The indexer logs job IDs/upload IDs, extraction failures, embedding batch failures, and sweep summaries, but must not log document contents or credentials. The agent logs should include upstream status and request failures without logging bearer tokens.

For systemd, use `journalctl -u kibegi-api`, `journalctl -u kibegi-ai-indexer`, and `journalctl -u kibegi-agent`. For Docker Compose, use `docker compose logs --tail=200 kibegi-api kibegi-ai-indexer kibegi-agent`. Configure log rotation at the host/container layer.

## AI indexing operations

The preferred path is the asynchronous Go callback after each successful upload. The indexer’s polling runner remains available as a recovery mechanism:

```bash
cd services/ai-indexer
. .venv/bin/activate
python3 -m app.worker_runner
```

A one-off batch can be triggered with an authenticated request to `POST /v1/index/process-due` and a body such as `{"limit": 100, "include_done": false}`. Inspect `GET /v1/index/jobs/{upload_id}` when a user reports missing AI search context. Pending, failed, and stale processing jobs should be retried only after checking object-storage availability and provider errors.

## Backups

Back up PostgreSQL using a consistent database backup procedure, preserve MinIO/S3 objects, and store encrypted copies separately from the host. A code rollback does not restore database rows or objects. Before schema or provider changes, record the current Git commit, environment version, database backup identifier, and object-storage backup status.

## Rollback

For an application rollback, stop or drain the affected process, restore the previous container/systemd artifact, verify the database connection and health endpoint, and replay a small read-only smoke test. Do not roll back the Go binary while applying an incompatible database schema change. The documented pre-cleanup source tag is `pre-go-primary-cleanup-6148d29`; current code rollback should use the Git history on `master`.

## Incident checklist

Capture UTC time, request ID, endpoint, status, service logs, dependency health, current commit, and whether the failure affects reads, writes, uploads, indexing, or MCP. Check database pool saturation, Redis errors, MinIO reachability, provider response codes, disk space, and process restarts before changing code or deleting data.
