# `internal/platform`

## Purpose

This directory contains infrastructure adapters shared by domain apps. Platform packages do not register routes or decide business permissions. They expose small, testable interfaces for PostgreSQL, Redis, HTTP responses/middleware, MinIO/S3, SMTP, and SendAfrica.

## Packages

| Package | Responsibility |
|---|---|
| `cache` | Pooled Redis client, JSON cache helpers, atomic counters, rate limits, locks, and deletion. |
| `database` | PostgreSQL connection pool creation and bounded pool settings. |
| `email` | SMTP message construction and delivery. |
| `httpx` | Standard JSON envelope and response writer. |
| `middleware` | Request IDs, access logs, panic recovery, CORS, timeouts support, and rate limiting. |
| `sms` | SendAfrica provider adapter and SMS formatting. |
| `storage` | MinIO/S3 put/open/stat/remove/public URL operations. |

## Rules

Platform adapters should return explicit configuration or provider errors and must not log secrets. Redis helpers should use bounded TTLs and atomic operations. Storage adapters must reject unconfigured operations rather than fabricate URLs or success states. HTTP middleware must preserve response envelopes and request IDs. Any change to an adapter should include focused tests plus the full repository suite.
