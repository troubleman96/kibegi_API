# `internal/apps`

## Purpose

This directory preserves the former domain boundaries as Go packages. Each first-level directory owns one business area and mirrors the corresponding API namespace. Domain packages contain HTTP handlers, repositories, payload structs, validation, transactions, and domain-specific tests.

## Package conventions

`handlers.go` owns path dispatch and response behavior. `repository.go` owns PostgreSQL queries and row mapping. Public handlers are separated when the same domain has unauthenticated token routes. App values receive shared dependencies through explicit structs rather than global variables.

Handlers should authenticate through the shared authentication package, obtain the user ID from request context, validate input before SQL, map `sql.ErrNoRows` to a domain not-found result, and return the standard HTTP envelope. Repositories must preserve existing table names, identifier types, ownership filters, and transaction semantics.

## Domain packages

| Package | Responsibility |
|---|---|
| `ai` | AI settings, usage, conversations, messages, and processing status. |
| `assignments` | Lecturer assignments, submissions, grading, and feedback. |
| `authentication` | JWT, password, registration, OTP, profiles, and authorization middleware. |
| `channel` | Channels, memberships, wallets, broadcasts, and public invite routes. |
| `classcomms` | Class profiles, contacts, representatives, wallets, broadcasts, and public registration. |
| `classes` | Classes, membership, search, join/leave, and QR. |
| `core` | Health/readiness endpoint. |
| `files` | Legacy unified-file compatibility over uploads and sharing. |
| `friends` | Friendships, requests, transitions, nicknames, and removal. |
| `library` | Categories, items, search, upload/download, and counters. |
| `marketplace` | Categories, listings, search, purchases, and orders. |
| `notifications` | Notification reads, unread counts, read state, and deletion. |
| `schedule` | Calendars, events, public feeds, sharing, QR, and SMS accounts. |
| `search` | Global search, suggestions, and history. |
| `sharing` | File shares, requests, transitions, and downloads. |
| `sms` | Generic-owner SMS accounts, top-ups, and delivery history. |
| `storage` | Quotas, usage recalculation, and history. |
| `uploads` | Multipart upload lifecycle and object streaming. |

## Change workflow

When adding a feature, inspect the preserved route contract, add repository methods, add handler dispatch and envelope behavior, wire dependencies in `cmd/kibegi-api/main.go`, add tests for validation/authorization/not-found cases, update the relevant folder README, and run the complete Go verification suite. Do not import Python or reconstruct removed Django models; use the existing PostgreSQL table contract directly.
