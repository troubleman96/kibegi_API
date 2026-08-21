# `internal/platform/storage`

## Responsibility

This package wraps MinIO/S3-compatible object storage for put, open, stat, remove, and public URL operations.

## Configuration

The adapter normalizes endpoints with or without a scheme, applies secure transport settings, and stores bucket/public-base configuration. `Configured()` distinguishes a usable client from an intentionally absent local-development configuration. Unconfigured put/open/stat/remove operations return an explicit error.

## Object safety

Domain handlers construct controlled object names and apply filename base-name sanitization before calling `Put`. The adapter does not authorize users; handlers must perform database ownership/membership checks first. `PublicURL` is presentation-only and must not be used to bypass private download authorization.

## Integrations

Uploads, files, sharing, library, authentication profile images, and the AI indexer all depend on the same bucket/object-key contract. Keep object keys stable when refactoring code and verify orphan cleanup after database failures.
