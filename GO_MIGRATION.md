# Kibegi API Go Migration

## Purpose

This document defines the migration path from the existing Django REST API to Go without breaking the current UI contract or requiring a risky all-at-once rewrite. The migration is intentionally incremental: the Django service remains the production reference while Go endpoints are introduced behind the same `/api/v1/` namespace and validated against the existing behavior.

## Current baseline

The repository is a Django REST API for the Kibegi digital school platform. It currently exposes authentication, classes, uploads and files, sharing, friends, notifications, storage, schedules, marketplace, library, channels, class communications, SMS, assignments, search, and AI endpoints. The project uses JWT authentication, PostgreSQL or SQLite, Redis when configured, S3-compatible MinIO storage, SendAfrica SMS, email delivery, and an OpenAI-compatible AI gateway.

The current endpoint surface is broad enough that a direct rewrite would create unnecessary compatibility and data-integrity risk. The migration therefore preserves the database and API contracts first, and replaces implementation domain by domain.

## Target architecture

The Go service will use the standard `net/http` stack initially, with small internal packages organized by responsibility:

| Concern | Initial Go boundary |
|---|---|
| Process entrypoint and lifecycle | `cmd/kibegi-api` |
| Environment configuration | `internal/config` |
| HTTP routing and handlers | `internal/apps/<app>` |
| Domain services | `internal/apps/<app>` |
| Persistence interfaces and PostgreSQL implementations | `internal/apps/<app>` plus shared database helpers |
| Shared response and middleware primitives | `internal/platform/httpx`, `internal/platform/middleware` |
| Redis cache, locks, rate limits, and queue primitives | `internal/platform/cache` |
| Database migrations | `db/migrations` |
| External providers | `internal/platform/providers` |

PostgreSQL will be the canonical database for the Go service. The existing Django database schema should be treated as an external contract during the transition. Go models and queries will be introduced against the existing tables rather than changing table names or identifiers without an explicit compatibility migration.

## App boundaries and performance strategy

The Django app structure remains a first-class Go boundary. The target layout uses `internal/apps/authentication`, `internal/apps/classes`, `internal/apps/uploads`, `internal/apps/sharing`, and the corresponding package for every existing Django app. Shared infrastructure is kept outside those domains so the modules remain independently testable and can be migrated or routed separately.

Redis is used aggressively where it improves latency without becoming the source of truth. It provides response caching for safe read endpoints, short-lived lookup and OTP state, rate limiting, idempotency keys, distributed locks, cache invalidation, and future queue coordination. PostgreSQL remains authoritative for users, memberships, balances, files, schedules, and other durable records. Every cache hit has a bounded TTL, every write invalidates affected keys, and correctness-sensitive operations use transactions plus Redis locks or idempotency keys where needed.

The Go database pool is bounded and reusable, with environment-controlled maximum open and idle connections plus connection lifetimes. Redis uses a pooled client with configurable pool size and minimum idle connections. These defaults are intended for production throughput but remain overrideable for each deployment environment.

## Compatibility rules

The Go implementation must preserve the following until the UI has migrated:

1. Existing URL paths, trailing slash behavior, HTTP methods, status codes, and content types.
2. The shared response envelope: `success`, `message`, `data`, and `errors`.
3. JWT access and refresh token semantics, including the one-hour access lifetime and seven-day refresh lifetime currently configured in Django.
4. Existing UUID and integer identifier formats.
5. Existing file URLs and S3/MinIO object keys.
6. Existing error behavior for authorization, validation, missing resources, and database failures.

Contract tests should be added for each migrated endpoint before routing production traffic to Go. During the transition, the same request should be replayable against both implementations and compared after removing intentionally nondeterministic fields such as timestamps and provider-generated URLs.

## Migration order

The recommended order is based on dependency depth and operational risk:

| Stage | Domain | Reason |
|---:|---|---|
| 0 | Health and observability | Establishes the Go process, deployment, logging, and readiness contract. |
| 1 | Authentication and users | Provides the identity boundary required by nearly every protected domain. |
| 2 | Classes and memberships | Supplies the central academic relationships used by files, schedules, and assignments. |
| 3 | Uploads, files, storage, and sharing | Moves the high-value file workflows while preserving MinIO object compatibility. |
| 4 | Friends and notifications | Adds relationship and event behavior around the core user model. |
| 5 | Schedules and SMS | Introduces public tokens, ICS generation, credits, and scheduled delivery. |
| 6 | Marketplace and library | Migrates independent catalog and transaction domains. |
| 7 | Channels and class communications | Migrates broadcast wallets, memberships, and delivery workflows. |
| 8 | Assignments, search, and AI | Migrates cross-domain and provider-heavy features last. |
| 9 | Django retirement | Removes Django only after endpoint parity, data verification, and production soak time. |

## First implemented slice

The first slice adds a compilable Go service with:

- Go module metadata and PostgreSQL driver support.
- Environment-backed HTTP, PostgreSQL pool, and Redis configuration.
- `GET /api/v1/health/` with the existing Kibegi response envelope.
- Database readiness checking through `PingContext`.
- Optional Redis readiness checking through a pooled client.
- App-scoped core package at `internal/apps/core`.
- Shared JSON response primitives at `internal/platform/httpx`.
- JSON structured logging, request timeouts, and graceful shutdown.
- Focused tests for the legacy health response, method handling, and safe Redis omission.

The endpoint deliberately reports `503 Service Unavailable` when `DATABASE_URL` is missing or the database cannot be reached. The response shape remains compatible with the Django implementation, including its current `success: true` envelope on the unhealthy branch.

## Next implementation slice

The next slice should introduce request ID and structured access-log middleware, Redis-backed cache and rate-limit helpers, and JWT verification. After that, authentication should be migrated endpoint-by-endpoint, beginning with profile reads and login before registration, OTP, password reset, Google login, and logout. No existing Django endpoint should be removed until its Go equivalent has contract tests and a controlled routing switch.

## Local commands

```bash
# Run Go tests
go test ./...

# Build the service
go build -o bin/kibegi-api ./cmd/kibegi-api

# Run the health endpoint locally
DATABASE_URL='postgres://user:password@localhost:5432/kibegi_db?sslmode=disable' \
  HTTP_ADDR=':8080' \
  ./bin/kibegi-api
```
