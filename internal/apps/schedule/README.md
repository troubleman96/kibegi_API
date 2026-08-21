# `internal/apps/schedule`

## Responsibility

The schedule package owns private calendars, events, event CRUD, sharing, QR responses, public schedule information, ICS/webcal feeds, and per-user schedule SMS accounts.

## Private operations

Private calendar and event handlers scope records to the authenticated owner or permitted class relationship. Calendar updates invalidate schedule cache namespaces. Event creation and updates preserve recurrence, days, reminders, source, and time-zone-aware timestamps. Event deletion must verify calendar ownership before issuing SQL.

## Public operations

Public routes use share tokens or calendar codes. They expose information and ICS downloads without exposing private credentials. Public access logs record access type, IP, user agent, and calendar ID for operational visibility. Webcal URLs use the configured frontend/API base URL and preserve trailing slash behavior.

## Reminder integration

The Go schedule package contains the reminder dispatcher that finds due events, checks SMS account balance, sends through the shared provider, consumes one credit conditionally, and writes delivery logs. The dispatcher can run from a worker or scheduled process without changing the HTTP route contract.
