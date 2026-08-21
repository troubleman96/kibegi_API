# `internal/apps/search`

## Responsibility

The search package owns global search, suggestions/autocomplete, authenticated search history, and history clearing under `/api/v1/search/`.

## Search sources

Global search combines users, classes, files, friends, and library records according to the authenticated user’s visibility. Each source must preserve ownership and membership filters. Suggestions should be bounded by query length and result count to avoid expensive wildcard scans.

## History and caching

Search history is durable in `search_searchhistory` and scoped to the current user. Redis may cache safe suggestions or result pages with bounded TTLs, but history writes and deletes must remain PostgreSQL-authoritative and invalidate user-specific keys. Do not store sensitive full query content in logs.
