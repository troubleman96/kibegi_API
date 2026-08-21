# `internal/apps/files`

## Responsibility

The files package preserves the unified-file compatibility namespace at `/api/v1/files/`. It delegates durable file data to the uploads and sharing tables rather than creating a duplicate file model.

## Routes and modes

The package serves all-files, my-uploads, shared-with-me, deleted, detail, restore, and permanent-delete paths. It shapes compatibility payloads from `uploads.Upload` data and marks shared results when they originate from accepted sharing records.

## Authorization

Every list and detail query is scoped to the authenticated user through uploader ownership, class membership, or accepted share status. Restore and permanent deletion require the original uploader’s authorization. Keep this package thin; changes to object streaming, upload lifecycle, or MinIO behavior belong in `uploads` and the shared storage adapter.
