# `internal/apps/notifications`

## Responsibility

The notifications package owns notification listing, unread count, mark-read, mark-all-read, and deletion under `/api/v1/notifications/`.

## Data and cache

Notifications are durable PostgreSQL rows. Unread counts are safe to cache briefly in Redis, but every read-state mutation must invalidate the user’s count and list keys. Never use a cached unread count to authorize a write or infer that a notification exists.

## Integration

Sharing, friendships, uploads, assignments, schedules, and other domains may create notifications. Creation should use a consistent type and payload shape. Notification handlers scope reads and mutations to the authenticated user and map missing records to the preserved not-found response.
