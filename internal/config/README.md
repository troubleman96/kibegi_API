# `internal/config`

## Responsibility

This package converts environment variables into the runtime configuration consumed by the Go composition root. It owns HTTP address, PostgreSQL pool, Redis pool, JWT, MinIO, SMTP, SMS, AI, media URL, timeout, and shutdown settings.

## Design

Configuration is loaded once at process startup. Defaults are conservative for local development and can be overridden by environment variables. Parsing should fail clearly for invalid durations, sizes, or required secrets. Do not read environment variables inside individual handlers; pass a configured dependency or value from `main.go`.

## Operational rules

Keep `.env.example` synchronized with fields in `config.go`. Add new variables to the configuration README and deployment guide. Never log complete configuration values because URLs can contain credentials and provider keys are secrets. Use separate service credentials for Go-to-indexer callbacks and the agent gateway.
