# `internal/apps/core`

## Responsibility

The core package owns the `/api/v1/health/` endpoint and shared health payload behavior.

## Readiness semantics

The endpoint checks PostgreSQL connectivity and reports Redis status when a Redis client is configured. Missing database configuration or failed database ping returns HTTP `503` while preserving the standard Kibegi envelope and diagnostic check fields. A health result is not a liveness guarantee for MinIO, SMTP, SMS, or embeddings unless those dependencies are explicitly included in the check configuration.

## Operational use

Use the endpoint for reverse-proxy health checks and deployment smoke tests. Do not make it perform expensive queries, mutate data, or expose credentials. Keep timestamps and error details bounded and safe for operator visibility.
