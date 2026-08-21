# Kibegi Data Model and Persistence

## Database authority

PostgreSQL is authoritative for all durable state. The Go service connects to the existing Kibegi schema and uses the table names and identifiers already consumed by the platform. The cleanup removed the former Django source code, not the database schema. No Go startup path runs schema migrations or destructive DDL.

Repositories use `database/sql` through a shared `pgx` pool. Each repository owns SQL for its app and maps database rows into Go payload structs. Write operations that affect balances, memberships, purchases, uploads, sharing state, or counters should use transactions and conditional updates where duplicate requests could otherwise create incorrect state.

## Identifier conventions

| Data | Identifier |
|---|---|
| Users | Existing integer `authentication_user.id`. |
| Classes | Existing UUID `classes_class.id`. |
| Uploads | Existing UUID `uploads_upload.id` plus unique short `file_code`. |
| Shares | Existing UUID `sharing_sharedfile.id`. |
| AI conversations/messages/chunks | Existing UUID values. |
| Schedule records | Existing integer IDs for calendars/events and UUID/token fields where defined by the schema. |
| Friendships and notifications | Existing integer IDs. |
| Marketplace and library records | Existing UUID or short code fields according to the existing table. |
| SMS generic ownership | Existing Django content-type model lookup plus owner object ID. |

## Core table families

The main table families are `authentication_*`, `classes_*`, `uploads_*`, `sharing_*`, `storage_*`, `schedule_*`, `marketplace_*`, `library_*`, `channel_*`, `classcomms_*`, `assignments_*`, `ai_*`, `search_*`, `notifications_*`, `friends_*`, and `sms_*`. The SMS repository also references `django_content_type` because generic-owner accounts preserve the existing content-type relationship.

The table prefix is part of the compatibility contract. Renaming a table, changing a column type, or replacing an integer with a UUID would require an explicit migration and a dual-read/dual-write plan; do not make such changes inside a handler patch.

## Object storage

`uploads_upload.file` contains the object key used by MinIO/S3. The Go storage adapter preserves keys such as `uploads/<user-id>/<filename>` and supports put, open, stat, remove, and public URL operations. Database rows and objects must be treated as a pair: a successful upload writes the object first and the row second; a failed row insert removes the orphan object; a permanent delete removes the row-authorized object after the database operation.

The AI indexer reads the same `file` object key. It does not infer paths from filenames or create a second storage convention.

## Storage quotas

`storage_userstorage` records a user’s quota and current usage. Recalculation aggregates non-deleted upload sizes from `uploads_upload.file_size`, updates the quota record, and writes a usage snapshot to `storage_storageusagehistory`. Redis caches safe quota reads with bounded TTLs and invalidates the user-specific cache after recalculation or relevant upload mutations.

## AI processing tables

The FastAPI indexer uses the existing AI tables:

| Table | Role |
|---|---|
| `ai_aiprocessingjob` | One processing state per upload: `pending`, `processing`, `done`, or `failed`. |
| `ai_documentchunk` | Ordered extracted text chunks, token counts, and JSON embeddings. |
| `ai_aiprofile` | Per-user provider key and model configuration. |
| `ai_aiconversation` / `ai_aimessage` | AI conversation and message history. |
| `ai_aiusage` | Daily and total token accounting. |

Indexing is idempotent. A Redis upload lock prevents concurrent work, completed jobs with chunks are skipped unless forced, stale processing jobs can be retried, and failed jobs retain a bounded error message.

## Redis authority rules

Redis never replaces PostgreSQL for durable business records. It stores cache entries, rate-limit counters, short-lived OTP state, refresh-token revocations, distributed locks, and coordination keys. Every cache key has a bounded TTL. Every write path that changes a cached resource must invalidate the related key or namespace. If Redis is unavailable, handlers should either bypass non-critical caching or return a dependency error for operations that require atomic coordination.

## Transaction and integrity rules

Use conditional SQL for credit consumption, e.g. update a balance only when sufficient credits remain, and inspect affected rows before reporting success. Use database transactions for multi-record operations such as purchases, membership changes with dependent state, share transitions that create notifications, and AI chunk replacement. Never report a successful durable write before the transaction commits.
