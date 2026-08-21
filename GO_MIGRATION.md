# Kibegi Django-to-Go API Migration

## Purpose and migration policy

This document records the incremental migration of the Kibegi Django REST API to Go. The migration preserves the existing Django service and files, uses the same `/api/v1/` URL space, and treats the Django PostgreSQL schema, object keys, identifiers, response envelopes, and client-visible behavior as compatibility contracts. Go is introduced domain by domain; Django retirement remains a separately controlled operational decision after production soak and rollback validation.

> **Compatibility rule:** The Go service runs alongside Django and does not delete or replace Django source files. Existing Django tables remain the durable source of truth during the transition.

## Target architecture

The Go service uses Go 1.22, the standard `net/http` stack, PostgreSQL through a pooled `database/sql` connection, Redis through a pooled `redis/go-redis/v9` client, MinIO/S3-compatible storage, SMTP email delivery, SendAfrica SMS, Django-compatible JWT claims, PBKDF2 password verification, UUID identifiers, and a shared response envelope.

| Concern | Go boundary | Compatibility responsibility |
|---|---|---|
| Process lifecycle and route registration | `cmd/kibegi-api` | Preserves Django URL prefixes and trailing-slash conventions. |
| Django app modules | `internal/apps/<app>` | Maintains one Go package per Django app, including `files`, `sms`, and `storage`. |
| PostgreSQL | `internal/platform/database` plus app repositories | Uses existing Django table names and identifiers; no schema-destructive SQL was introduced. |
| Redis | `internal/platform/cache` | Provides bounded response caching, atomic counters, rate-limit windows, distributed locks, token revocation, and cache invalidation. |
| Object storage | `internal/platform/storage` | Preserves MinIO/S3 object names and supports streaming upload/download/delete operations. |
| HTTP behavior | `internal/platform/httpx`, `internal/platform/middleware` | Preserves the `success`, `message`, `data`, and `errors` envelope and adds request IDs, access logs, panic recovery, CORS, timeouts, and Redis-backed rate limiting. |
| External providers | `internal/platform/email`, `internal/platform/sms` | Preserves SMTP OTP delivery and SendAfrica SMS integration, with unconfigured-provider behavior suitable for local development. |

## Completed app migrations

All major Django domains are now represented in Go and registered under the preserved API namespace. Authentication includes login, registration, verification and resend OTP flows, password reset, JWT refresh/logout, change-password, profile reads and updates, Google token exchange, profile-image upload/removal, phone OTP verification, lecturer approval, and root-level compatibility shortcuts. The `files` package preserves the legacy unified-file namespace over upload and sharing data, while `uploads` remains the native upload domain.

| Django app | Go package | Registered namespace | Principal coverage |
|---|---|---|---|
| `core` | `internal/apps/core` | `/api/v1/health/` | Database and Redis readiness. |
| `authentication` | `internal/apps/authentication` | `/api/v1/auth/`, `/register/`, `/login/` | JWT-compatible authentication, profile, OTP, Google, lecturer, phone, and profile-image flows. |
| `classes` | `internal/apps/classes` | `/api/v1/classes/` | Listing, creation, search, join, leave, detail, members, and QR. |
| `uploads` | `internal/apps/uploads` | `/api/v1/uploads/` | Multipart upload, listing, search, trash, recent, restore, permanent delete, and MinIO download. |
| `files` | `internal/apps/files` | `/api/v1/files/` | Unified all-files, own uploads, shared-with-me, deleted, detail, restore, and permanent-delete compatibility routes. |
| `storage` | `internal/apps/storage` | `/api/v1/storage/` | Quota creation, current usage, detailed info, recalculation, history, and Redis response caching. |
| `sharing` | `internal/apps/sharing` | `/api/v1/sharing/` | Share, bulk-share, accept/reject, sent/received/request lists, detail, and download. |
| `notifications` | `internal/apps/notifications` | `/api/v1/notifications/` | List, unread count, read state, read-all, deletion, and Redis caching. |
| `friends` | `internal/apps/friends` | `/api/v1/friends/` | Search, requests, accept/decline/cancel, nickname, and removal. |
| `schedule` | `internal/apps/schedule` | `/api/v1/schedule/`, `/api/v1/public/schedule/` | Calendars, events, sharing, ICS/webcal, QR, SMS account, and public access. |
| `marketplace` | `internal/apps/marketplace` | `/api/v1/marketplace/` | Categories, listings, search, CRUD, atomic purchases, and order history. |
| `library` | `internal/apps/library` | `/api/v1/library/` | Categories, browsing, search, upload, download, and counters. |
| `channel` | `internal/apps/channel` | `/api/v1/channel/`, `/api/v1/public/channel/` | Channel CRUD, membership, join, wallet, broadcasts, public info, and public join. |
| `classcomms` | `internal/apps/classcomms` | `/api/v1/class-comms/`, `/api/v1/public/class-comms/` | Profiles, contacts, wallets, broadcasts, public registration info, and public contact registration. |
| `assignments` | `internal/apps/assignments` | `/api/v1/assignments/` | Lecturer assignment CRUD, student draft/submit, grading, and feedback. |
| `ai` | `internal/apps/ai` | `/api/v1/ai/` | Settings masking, usage, conversations, messages, and processing status. |
| `search` | `internal/apps/search` | `/api/v1/search/` | Global search, suggestions, search history, and history clearing. |
| `sms` | `internal/apps/sms` | `/api/v1/sms/` | Generic-owner account detail, atomic credit top-up, and delivery history. |

## Data and performance guarantees

PostgreSQL remains authoritative for users, memberships, balances, uploads, sharing records, schedules, catalog records, and all other durable state. The Go repositories query the existing Django table names directly. Storage quota recalculation preserves the Django service behavior by summing `uploads_upload.file_size` for the user, while Redis caches safe read responses with bounded TTLs and invalidates affected keys on writes.

Redis is used as an accelerator and coordination layer rather than as a replacement for durable state. The service uses pooled connections, atomic rate-limit counters, distributed locks where domain operations require coordination, profile and notification caching, refresh-token blacklist keys, search/storage caches, and cache invalidation. When Redis is not configured, the service remains able to serve non-cache-dependent paths and reports the missing readiness component through health checks.

The database pool has configurable maximum open and idle connections, connection lifetimes, and idle timeouts. The object-storage adapter preserves object names used by Django uploads and supports MinIO/S3-compatible deployments. No migration code introduces `DROP TABLE`, `ALTER TABLE`, `TRUNCATE`, or `CREATE TABLE` statements in the Go service.

## Verification completed

The following checks were executed against the current `master` worktree. The final repository state was clean and synchronized with `origin/master`.

| Verification | Result |
|---|---|
| `GOTOOLCHAIN=local go test ./...` | Passed across all Go packages. |
| `GOTOOLCHAIN=local go test -race ./...` | Passed. |
| `GOTOOLCHAIN=local go build -o /tmp/kibegi-api ./cmd/kibegi-api/` | Passed. |
| `GOTOOLCHAIN=local go vet ./...` | Passed. |
| `git diff --check` | Passed before the final pushed slices. |
| Route inventory comparison | Django app mounts and Go app mounts now cover the preserved API namespaces, including `files`, public channel/class-comms, SMS, storage, authentication extras, and root compatibility shortcuts. |
| Isolated HTTP smoke test | Passed for health response behavior, request IDs, CORS preflight (`204`), and unauthenticated protected-route rejection (`401`). |
| Data-integrity static scan | No schema-destructive SQL found in Go sources; existing Django table names are referenced directly. |

The health endpoint correctly returns `503 Service Unavailable` when `DATABASE_URL` is absent, while retaining the Django-compatible envelope. A real deployment verification must repeat the smoke tests with production-like PostgreSQL, Redis, MinIO, SMTP, and SendAfrica credentials because the isolated test intentionally ran without those services.

## Runtime configuration

Set `DATABASE_URL`, `SECRET_KEY`, and `HTTP_ADDR` for the minimum service runtime. Configure `REDIS_URL` to enable response caching, rate limiting, refresh-token revocation, and distributed coordination. Configure the MinIO variables for file/profile-image operations, SMTP variables for email OTP and approval notifications, and `SENDAFRICA_API_KEY`, `SENDAFRICA_BASE_URL`, and `SENDAFRICA_SENDER_ID` for SMS delivery. Set `KIBEGI_CORS_ORIGIN` to the deployed frontend origin instead of relying on the development wildcard.

The recommended local commands are:

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

## Controlled cutover readiness

The migration is **code-complete for the current route surface**, but Django retirement is not an automatic consequence of a green build. The recommended cutover is reversible and staged. First deploy Go beside Django against a replicated or otherwise protected database connection, then replay representative authenticated and unauthenticated requests against both implementations. Compare response envelopes, status codes, identifiers, authorization decisions, file URLs, and durable write effects while ignoring timestamps and provider-generated identifiers.

Next, route a small percentage of read traffic to Go, monitor health, latency, PostgreSQL pool saturation, Redis error rates, object-storage failures, SMS/email provider errors, and application logs, and keep Django available as the immediate rollback target. Increase traffic only after the soak window shows no contract or integrity regressions. Write traffic for balances, purchases, membership changes, uploads, sharing, and schedule mutations should be switched only after idempotency and duplicate-write behavior has been validated in the deployment environment.

Django source files and Django route definitions must remain in place during the soak period. Retirement should occur only after an explicit rollback plan, database backup, provider credential validation, observability dashboards, and stakeholder sign-off are complete. If any parity regression appears, restore the Django route switch, preserve the Go logs and request IDs for diagnosis, and do not apply schema changes as an emergency workaround.

## Incremental push history

The migration was pushed incrementally to `origin/master`. The recent parity and verification slices include the following commits:

| Commit | Change |
|---|---|
| `315ee6d` | Global search and history migration. |
| `be4ce0e` | SMS account and delivery endpoints. |
| `aae701d` | Storage quota tracking endpoints. |
| `37db0b5` | Public channel and class-comms route preservation. |
| `ac3606d` | Public class-comms registration. |
| `1956743` | Legacy files compatibility endpoints. |
| `d7a05fa` | Authentication parity endpoints. |
| `53d6f8c` | Profile-image and auth compatibility routes. |
| `dcec376` | CORS and Redis rate limiting. |

The current migration branch is `master`, and every listed slice was formatted, tested, built where applicable, committed, and pushed before the next slice was started.

## Python support services

The Go API remains the primary domain backend. Two narrowly scoped Python services now complement it without restoring Django as the public API implementation.

| Service | Location | Responsibility |
|---|---|---|
| FastAPI AI indexer | `services/ai-indexer` | Downloads upload objects from MinIO/S3, extracts supported document formats, writes `ai_documentchunk`, updates `ai_aiprocessingjob`, and optionally generates embeddings through the Ngamia-compatible OpenAI endpoint. |
| FastAPI/FastMCP gateway | `services/kibegi-agent` | Exposes an authenticated Python gateway and FastMCP HTTP tools over the complete allowlisted Go API namespace while forwarding end-user JWTs. |

The Go upload handler can asynchronously notify the indexer through `AI_INDEXER_URL` and `AI_INDEXER_TOKEN`. The indexer also provides a batch endpoint and an optional polling runner for pending, failed, and stale jobs. Redis locks prevent duplicate upload processing. The gateway requires explicit confirmation for mutation calls and rejects paths outside the migrated `/api/v1/` namespaces.

The support services were syntax-checked and imported successfully, their unit tests passed, and isolated HTTP smoke tests verified indexer service-token rejection (`401`), missing-database handling (`503`), gateway proxy operation, invalid-path rejection (`400`), and FastMCP endpoint startup. Production verification still requires real PostgreSQL, Redis, MinIO/S3, and embedding credentials.

Django has **not** been deleted. It remains the rollback/reference implementation until the new support services and the Go backend complete an environment-backed soak test and the user explicitly authorizes destructive cleanup.
