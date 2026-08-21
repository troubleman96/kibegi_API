# `cmd`

This directory contains executable entrypoints for Kibegi services. The current production entrypoint is [`kibegi-api/`](kibegi-api/), which composes the Go API, infrastructure adapters, domain apps, middleware, and graceful shutdown behavior.

Add a new executable here only when it represents a separately supervised process with a clear dependency boundary. Keep reusable domain logic in `internal/` and document startup, environment variables, ports, health checks, and deployment ownership in the entrypoint’s local README.
