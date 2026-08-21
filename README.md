# Kibegi Backend

Kibegi is a Go-primary backend for the digital school platform. The public domain API is implemented in Go 1.22 using `net/http`, PostgreSQL pooling, Redis caching and coordination, MinIO/S3-compatible object storage, SMTP, SendAfrica SMS, JWT-compatible authentication, and the existing Django database schema.

## Repository layout

| Component | Location | Purpose |
|---|---|---|
| Go API entrypoint | `cmd/kibegi-api/` | Starts the primary HTTP backend and registers all API namespaces. |
| Go domain apps | `internal/apps/` | One Go package per preserved domain: authentication, classes, uploads, files, sharing, storage, friends, notifications, schedules, marketplace, library, channels, class communications, assignments, AI, search, SMS, and core health. |
| Shared platform | `internal/platform/` | PostgreSQL, Redis, HTTP envelopes/middleware, MinIO/S3, SMTP, and SMS providers. |
| AI indexing service | `services/ai-indexer/` | FastAPI sidecar that extracts upload text, chunks content, stores AI jobs/chunks, and optionally generates embeddings. |
| Agent/MCP gateway | `services/kibegi-agent/` | FastAPI gateway and FastMCP HTTP server exposing typed tools plus complete allowlisted access to the Go API. |

The Go API uses the existing Django PostgreSQL tables and object keys for data compatibility. Django source code is no longer part of the active backend path; the historical pre-cleanup implementation is retained only in the Git backup tag and archive described below.

## API coverage

The Go service preserves the migrated API namespaces and response envelope: `success`, `message`, `data`, and `errors`.

| Namespace | Coverage |
|---|---|
| `/api/v1/health/` | Database and Redis readiness. |
| `/api/v1/auth/` | Registration, OTP, login, JWT refresh/logout, password reset, password changes, profiles, Google, phone, lecturer approval, and profile images. |
| `/api/v1/classes/` | Class listing, search, creation, detail, membership, leave, and QR. |
| `/api/v1/uploads/` and `/api/v1/files/` | Uploads, search, trash, restore, permanent deletion, shared files, and downloads. |
| `/api/v1/storage/` | Quotas, usage, recalculation, detail, and history. |
| `/api/v1/sharing/` | Sharing, bulk sharing, requests, transitions, detail, and download. |
| `/api/v1/friends/` and `/api/v1/notifications/` | Friend workflows and notification workflows. |
| `/api/v1/schedule/` and `/api/v1/public/schedule/` | Calendars, events, sharing, ICS/webcal, QR, public feeds, and SMS accounts. |
| `/api/v1/marketplace/` and `/api/v1/library/` | Catalogs, listings, purchases, orders, library items, counters, and downloads. |
| `/api/v1/channel/` and `/api/v1/public/channel/` | Channel CRUD, memberships, wallets, broadcasts, public information, and invite joins. |
| `/api/v1/class-comms/` and `/api/v1/public/class-comms/` | Profiles, contacts, representatives, wallets, broadcasts, and public registration. |
| `/api/v1/assignments/`, `/api/v1/ai/`, `/api/v1/search/`, `/api/v1/sms/` | Assignments, AI settings/conversations/status, global search/history, SMS wallets, and delivery history. |

## Local Go setup

```bash
GOTOOLCHAIN=local go test ./...
GOTOOLCHAIN=local go test -race ./...
GOTOOLCHAIN=local go vet ./...
GOTOOLCHAIN=local go build -o bin/kibegi-api ./cmd/kibegi-api/

DATABASE_URL='postgres://user:password@localhost:5432/kibegi_db?sslmode=disable' \
SECRET_KEY='replace-with-a-long-random-secret' \
HTTP_ADDR=':8080' \
./bin/kibegi-api
```

Configure `REDIS_URL` for response caching, atomic counters, rate limiting, token revocation, distributed locks, and coordination. Configure the MinIO, SMTP, SendAfrica, and CORS variables in `.env.example` for production integrations.

## FastAPI AI indexer

The indexer is a separate Python service and does not run Django. It reads upload metadata from PostgreSQL, downloads the existing object key from MinIO/S3, extracts supported PDF, DOC/DOCX, TXT, Markdown, RTF, CSV, PPT/PPTX, and XLS/XLSX content, writes `ai_documentchunk` rows, and updates `ai_aiprocessingjob` states. The Go upload handler asynchronously calls the indexer through `AI_INDEXER_URL` and `AI_INDEXER_TOKEN`; the indexer also provides a batch endpoint and optional polling runner for retries and stale jobs.

```bash
cd services/ai-indexer
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## FastMCP agent gateway

The agent gateway forwards authenticated user JWTs to the Go API. It exposes typed tools for health, search, classes, uploads, downloads, storage, sharing, notifications, friends, schedules, marketplace, library, channels, class communications, assignments, AI status, and SMS. Its guarded generic API tool covers every allowlisted migrated route, including detail and mutation paths. All mutations require explicit confirmation.

```bash
cd services/kibegi-agent
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8091
```

The FastMCP HTTP endpoint defaults to `/mcp`. Deploy it behind TLS and an authentication layer before exposing it outside a trusted network. See `services/kibegi-agent/API_TOOL_COVERAGE.md` for the complete tool map and safety controls.

## Verification

The repository has been verified with Go unit tests, race-enabled Go tests, `go vet`, Go builds, Python compilation, FastAPI service imports, indexer extraction tests, agent gateway tests, and isolated HTTP smoke tests. The services must still be tested with deployment PostgreSQL, Redis, MinIO/S3, SMTP, SendAfrica, and embedding credentials before production rollout.

## Backup and rollback

The approved cleanup was created from commit `6148d29`. The complete pre-cleanup source snapshot is available under the Git tag `pre-go-primary-cleanup-6148d29` and the archive `kibegi_API-pre-go-primary-cleanup-6148d29.tar.gz`. Restoring the historical implementation is therefore possible without changing the active Go-primary branch.

## Documentation

The detailed documentation hub is [`docs/README.md`](docs/README.md). It links to architecture, API contracts, data persistence, configuration, security, operations, deployment, testing, AI indexing, agent/MCP, and troubleshooting guides.

Folder-level references are available at [`cmd/kibegi-api/README.md`](cmd/kibegi-api/README.md), [`internal/config/README.md`](internal/config/README.md), [`internal/apps/README.md`](internal/apps/README.md), [`internal/platform/README.md`](internal/platform/README.md), [`services/README.md`](services/README.md), [`services/ai-indexer/app/README.md`](services/ai-indexer/app/README.md), and [`services/kibegi-agent/app/README.md`](services/kibegi-agent/app/README.md). Each domain and infrastructure package also contains a local README describing its responsibility and extension rules.
