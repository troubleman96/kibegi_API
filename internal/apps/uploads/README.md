# `internal/apps/uploads`

## Responsibility

The uploads package owns native file creation and lifecycle operations: multipart upload, listing, search, trash, recent files, detail, download, restore, and permanent deletion. It is the only domain package that accepts the primary upload stream and writes objects to MinIO/S3.

## Upload transaction flow

The handler authenticates the user, parses the `file` multipart part and `class_obj` UUID, enforces the 50MB limit, derives a safe object key under `uploads/<user-id>/<filename>`, writes the object, inserts `uploads_upload`, and removes the object if the database insert fails. After commit, it asynchronously calls the FastAPI indexer with the new upload UUID; indexer failure does not invalidate a successful upload.

## Lifecycle rules

Normal deletion is soft deletion and moves an upload to trash. Restore and permanent-delete are separate authenticated operations. Permanent deletion checks uploader ownership, removes the database record, and removes the object. Downloads stream object bytes only after repository authorization verifies uploader, class membership, or accepted sharing.

## Caching and integration

Safe list responses may use Redis cache keys scoped by user, query, mode, and page. Upload, restore, trash, and permanent-delete mutations must invalidate affected list and storage quota caches. Sharing, files compatibility, storage, and AI indexing all depend on the upload table and object key contract.

## Configuration

Set `MINIO_*` variables for storage and `AI_INDEXER_URL`/`AI_INDEXER_TOKEN` for asynchronous indexing. When object storage is unavailable, upload and download operations return a dependency error rather than a fabricated URL.
