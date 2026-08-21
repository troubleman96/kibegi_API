# `internal/platform/middleware`

## Responsibility

This package provides shared HTTP controls: request IDs, access logging, panic recovery, CORS, timeout support, and Redis-backed client rate limiting.

## Request lifecycle

Request IDs are established before logging and are returned in response headers. Access logs record safe metadata and duration. Recovery converts panics into the standard envelope. CORS handles configured origins and preflight requests. Rate limiting uses atomic Redis counters keyed by client address and a short window; it should not log or trust arbitrary forwarded IP headers unless the reverse proxy is trusted.

## Change rules

Middleware must remain domain-agnostic and should not read business tables. Preserve response headers and status codes for preflight and errors. Any change to client-IP extraction, trusted proxy handling, allowed methods, or rate-limit policy requires a security review and updated tests.
