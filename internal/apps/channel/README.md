# `internal/apps/channel`

## Responsibility

The channel package owns standalone broadcast channels under `/api/v1/channel/` and public invite operations under `/api/v1/public/channel/`. It handles channel CRUD, members, join, wallet, broadcast creation/detail, public information, and public invite-token joins.

## Access rules

Channel creation, joining, member management, wallet changes, and broadcasts enforce authentication and the channel’s visibility/management rules. The preserved behavior requires a phone number and verified phone for operations that can send SMS or alter channel membership. Owners/managers may manage channels; owners cannot be removed.

## Wallet and broadcasts

Broadcast creation must validate recipients, available credits, provider configuration, and channel management access. Credit consumption must be conditional and durable. The repository writes broadcast status and delivery summary fields, while provider calls and delivery records remain observable. Public routes expose only invite-safe metadata and never wallet balances or private membership data.
