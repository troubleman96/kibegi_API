# `internal/platform/cache`

## Responsibility

This package wraps Redis for pooled connections, JSON cache reads/writes, atomic counters, rate-limit windows, distributed locks, token revocation, and cache invalidation.

## Usage rules

Every cache entry must have a bounded TTL and a key that includes the domain, version, user/resource scope, and relevant query/page dimensions. Writes must invalidate affected keys. Use atomic Redis operations for rate limits, credit coordination, and idempotency; do not implement read-modify-write counters in application memory.

## Failure behavior

When Redis is unconfigured, safe read handlers may bypass caching and the health endpoint reports the missing readiness component. Operations that require distributed coordination must return a dependency error or use a PostgreSQL transaction that preserves correctness. Never treat a Redis cache value as the durable source of business state.
