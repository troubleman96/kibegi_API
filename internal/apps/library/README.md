# `internal/apps/library`

## Responsibility

The library package owns library categories, item browsing, search, current-user items, item detail, upload, download, and view/download counters under `/api/v1/library/`.

## Storage and counters

Library item metadata is durable in PostgreSQL and binary content uses the shared MinIO/S3 adapter. Download and view counters must update atomically or tolerate retries without corrupting counts. Cache categories and safe item lists only with bounded TTLs and invalidation after uploads, updates, and deletion.

## Authorization

Item reads and downloads must enforce the existing visibility/class rules. Upload and detail mutations require authenticated ownership or the documented management role. Do not return private object credentials; use the storage adapter’s controlled URL or streaming response.
