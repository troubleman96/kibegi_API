# `internal/apps/friends`

## Responsibility

The friends package owns friend listing, user search, incoming and sent requests, add, accept, decline, cancel, nickname update, and removal under `/api/v1/friends/`.

## State transitions

Friendship operations use explicit statuses and actor checks. Add creates or updates the appropriate request state; accept/decline/cancel validate that the current user is the correct actor; remove affects an established friendship only. A transition should be idempotent where the existing contract permits it and should never allow one user to modify another user’s request.

## Integration

Friend actions can create notifications and feed global search results. Repository queries must scope by current user and preserve the existing integer friendship IDs. Nickname updates affect only the authenticated user’s representation of a friendship and should invalidate relevant friend list caches.
