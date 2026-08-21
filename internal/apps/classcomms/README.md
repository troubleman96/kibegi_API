# `internal/apps/classcomms`

## Responsibility

The class communications package owns class communication profiles, contacts, representatives, wallets, broadcasts, and public registration routes under `/api/v1/class-comms/` and `/api/v1/public/class-comms/`. The unhyphenated `/api/v1/classcomms/` alias remains supported.

## Authorization

Class owners, lecturers, and approved communications managers receive management access according to the existing class membership roles. Contact creation/deletion, representative promotion, wallet changes, and broadcast operations must verify class membership and management permission before SQL or provider calls.

## Broadcasts and registration

Broadcast creation stores a durable class broadcast and dispatches SMS according to wallet and phone rules. Detail responses include delivery summary fields without exposing provider secrets. Public registration endpoints expose only token-scoped class metadata and registration actions; they must not reveal private contact lists or wallet data.
