# `internal/apps/storage`

## Responsibility

The storage package owns per-user quota tracking under `/api/v1/storage/`. It reads and updates existing `storage_userstorage` and `storage_storageusagehistory` rows and calculates usage from non-deleted `uploads_upload.file_size` values.

## Operations

The handler supports current quota reads, detailed storage information, recalculation, and usage-history reads. Recalculation uses PostgreSQL as the authority, updates the quota record, writes a history snapshot, and invalidates user-scoped Redis cache entries.

## Integrity rules

Do not treat Redis usage values as durable. Do not add a second file-size counter that can drift from uploads. Any upload create, restore, soft-delete, or permanent-delete path that changes total usage should invalidate storage cache keys. Quota updates should remain transactionally consistent with history snapshots where the schema permits.
