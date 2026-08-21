# `cmd/kibegi-api`

## Responsibility

This directory contains the Go API executable entrypoint. `main.go` is the composition root: it loads environment configuration, opens shared dependencies, constructs every app package, registers the preserved routes, applies global middleware, starts the HTTP server, and handles graceful shutdown.

## Startup sequence

The process loads `internal/config`, opens the PostgreSQL pool, creates the Redis client, initializes MinIO/S3, SMTP, SendAfrica, and the JWT token service, then builds app values with repositories and shared dependencies. Missing optional providers are logged and exposed through affected operation failures or health checks rather than causing compile-time coupling.

Routes are registered under `/api/v1/` with public schedule/channel/class-comms handlers separated from authenticated handlers. Compatibility aliases include `/api/v1/classcomms/`, `/api/v1/auth/password-reset-confirm/`, `/register/`, and `/login/`.

## Middleware order

The composition root applies request timeout, Redis-backed rate limiting, CORS, panic recovery, access logging, and request IDs around the multiplexer. The order matters: request IDs should exist for logs and errors, recovery should cover handlers, and CORS should answer preflight before route dispatch.

## Running

```bash
GOTOOLCHAIN=local go build -o bin/kibegi-api ./cmd/kibegi-api/
HTTP_ADDR=:8080 DATABASE_URL='postgres://...' SECRET_KEY='...' ./bin/kibegi-api
```

Set `AI_INDEXER_URL` and `AI_INDEXER_TOKEN` to enable asynchronous upload indexing callbacks. Keep the entrypoint free of domain SQL; repository behavior belongs in the corresponding app package.
