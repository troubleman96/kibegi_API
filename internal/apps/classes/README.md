# `internal/apps/classes`

## Responsibility

The classes package owns class creation, listing, search, detail, membership, join/leave, members, and QR-related responses. It uses existing `classes_class` and `classes_membership` rows and enriches payloads with creator, member, file, and role information.

## Authorization

Class visibility and membership are enforced in repository queries and handlers. Public classes may be discoverable, but joining and leaving still require authentication and domain validation. A class creator cannot leave their own class. Membership transitions should be idempotent or return the documented conflict/not-member errors.

## Performance

List and search queries use bounded pagination and SQL filtering. Avoid loading all memberships or uploads into memory. Cache only safe reads when a relevant invalidation path exists. QR payloads should contain stable class identifiers or preserved client-facing URLs rather than internal database credentials.

## Route family

The package owns `/api/v1/classes/` for list/create, search, join, detail, members, leave, and QR behavior. Changes to membership must be coordinated with uploads, sharing, schedules, assignments, and class communications because those domains use class membership as an authorization boundary.
