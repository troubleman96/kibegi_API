# Schedule Frontend Integration Guide

This guide explains how the UI should integrate with the Kibegi schedule backend.

Yes: calendars are synced using ICS feeds.

The backend provides:
- private authenticated APIs for the owner to manage calendars and events
- public ICS endpoints for subscribing from calendar apps
- public metadata endpoints for a share/subscription screen
- QR generation for handing off the subscription URL to another device

## Base Routes

Authenticated schedule routes:
- `/api/v1/schedule/`

Public schedule routes:
- `/api/v1/public/schedule/`

## Core Idea

Each user automatically gets 2 calendars:
- `classes`
- `examination`

The frontend should treat these as the user's default schedule containers.

Users do not create extra calendars through this API. Instead, they:
- fetch their default calendars
- open one calendar
- create and manage events inside it
- optionally share or subscribe to that calendar through ICS

## Recommended UI Flow

### 1. Load the schedule home screen

Call:

```http
GET /api/v1/schedule/calendars/
Authorization: Bearer <token>
```

Use this to render:
- the list of user calendars
- event counts
- public sync enabled/disabled status

Example response shape:

```json
{
  "success": true,
  "message": "Schedule calendars retrieved successfully",
  "data": [
    {
      "id": 1,
      "name": "My Classes",
      "calendar_type": "classes",
      "description": "Default classes schedule for John Doe.",
      "is_public_sync": true,
      "calendar_code": "AB7K9Q",
      "event_count": 2,
      "created_at": "2026-04-09T10:00:00Z",
      "updated_at": "2026-04-09T10:00:00Z"
    },
    {
      "id": 2,
      "name": "My Examinations",
      "calendar_type": "examination",
      "description": "Default examination schedule for John Doe.",
      "is_public_sync": true,
      "calendar_code": "CD9M2X",
      "event_count": 1,
      "created_at": "2026-04-09T10:00:00Z",
      "updated_at": "2026-04-09T10:00:00Z"
    }
  ]
}
```

Frontend notes:
- store each calendar `id`
- use `calendar_type` to label the UI
- show `event_count` on cards/tabs

## 2. Open one calendar

Call:

```http
GET /api/v1/schedule/calendars/{calendarId}/
Authorization: Bearer <token>
```

Use this to render:
- calendar title
- description
- sync toggle state
- nested events

This response includes `events`, so it is a good first load for a detail page.

## 3. Load only events for a calendar

Call:

```http
GET /api/v1/schedule/calendars/{calendarId}/events/
Authorization: Bearer <token>
```

Use this when:
- refreshing the event list
- loading a calendar tab
- updating the UI after create/edit/delete

Events are returned ordered by start date/time.

## 4. Create an event

Call:

```http
POST /api/v1/schedule/calendars/{calendarId}/events/
Authorization: Bearer <token>
Content-Type: application/json
```

Example payload:

```json
{
  "title": "Linear Algebra",
  "description": "Matrices and vectors",
  "location": "Room 4B",
  "start_at": "2026-05-01T09:00:00Z",
  "end_at": "2026-05-01T10:30:00Z",
  "event_type": "class",
  "recurrence": "weekly",
  "days": ["monday", "wednesday"],
  "reminder_minutes": 20
}
```

Supported `event_type` values:
- `class`
- `exam`
- `study`
- `deadline`
- `meeting`
- `other`

Supported `recurrence` values:
- `none`
- `daily`
- `weekly`
- `monthly`

Validation rules:
- `end_at` must be after `start_at`
- if `recurrence = weekly`, then `days` must contain at least one weekday

Frontend notes:
- do not send `calendar` in the payload as the backend assigns it from the route
- use ISO datetime strings
- if your UI is local-time based, convert carefully before sending

## 5. View one event

Call:

```http
GET /api/v1/schedule/events/{eventId}/
Authorization: Bearer <token>
```

Use this for:
- event details drawer
- edit form prefill

## 6. Update an event

Call:

```http
PATCH /api/v1/schedule/events/{eventId}/
Authorization: Bearer <token>
Content-Type: application/json
```

Example payload:

```json
{
  "location": "Updated Hall",
  "reminder_minutes": 10
}
```

Frontend notes:
- partial updates are supported
- if changing recurrence to `weekly`, include `days`

## 7. Delete an event

Call:

```http
DELETE /api/v1/schedule/events/{eventId}/
Authorization: Bearer <token>
```

Recommended UI behavior:
- optimistic remove is okay if you also handle rollback
- simplest flow is delete, then refresh the event list

## 8. Update calendar settings

Call:

```http
PATCH /api/v1/schedule/calendars/{calendarId}/
Authorization: Bearer <token>
Content-Type: application/json
```

Useful fields:

```json
{
  "name": "Semester Classes",
  "description": "Main class timetable",
  "is_public_sync": true
}
```

Frontend notes:
- `calendar_type` is read-only
- `calendar_code` is read-only
- `is_public_sync` controls whether public ICS endpoints work

## Sharing and Subscription

This is where ICS comes in.

### 9. Get share/subscription links

Call:

```http
GET /api/v1/schedule/calendars/{calendarId}/share/
Authorization: Bearer <token>
```

Example response:

```json
{
  "success": true,
  "message": "Schedule share information retrieved successfully",
  "data": {
    "calendar_id": "1",
    "calendar_type": "classes",
    "calendar_code": "AB7K9Q",
    "subscribe_url": "https://api.example.com/api/v1/public/schedule/<token>/subscribe/",
    "download_url": "https://api.example.com/api/v1/public/schedule/<token>/download/",
    "webcal_url": "webcal://api.example.com/api/v1/public/schedule/<token>/subscribe/",
    "subscription_page_url": "https://api.example.com/api/v1/public/schedule/<token>/info/",
    "frontend_subscription_url": "https://app.example.com/schedule/subscribe/<token>",
    "code_lookup_url": "https://api.example.com/api/v1/public/schedule/code/AB7K9Q/info/"
  }
}
```

Meaning of each link:
- `subscribe_url`: raw ICS feed over HTTP/HTTPS
- `download_url`: downloads the ICS file
- `webcal_url`: best link for calendar apps that support `webcal://`
- `subscription_page_url`: backend public info page endpoint
- `frontend_subscription_url`: your app's share page if `SCHEDULE_FRONTEND_URL` is configured
- `code_lookup_url`: lets users find a calendar by short code

### 10. Show a QR code in the UI

Call:

```http
GET /api/v1/schedule/calendars/{calendarId}/qr/
Authorization: Bearer <token>
```

This returns:
- `Content-Type: image/png`

Use it when:
- desktop user wants to scan with phone
- you want a quick share panel

You can render it directly in the UI as an image source from the protected endpoint.

## Public Integration Flow

These endpoints do not require authentication.

### 11. Public info page by token

Call:

```http
GET /api/v1/public/schedule/{token}/info/
```

Use this for a frontend page like:
- "Subscribe to this calendar"
- "Open in Apple Calendar / Google Calendar / Outlook"

Recommended UI elements:
- calendar name
- calendar type
- event count
- subscribe button using `webcal_url`
- fallback copy button using `subscribe_url`
- download ICS button using `download_url`

### 12. Public info page by short code

Call:

```http
GET /api/v1/public/schedule/code/{code}/info/
```

Use this when your UI allows a user to manually enter a calendar code.

### 13. Subscribe via ICS

Call:

```http
GET /api/v1/public/schedule/{token}/subscribe/
```

This returns an ICS calendar feed with content type:

```text
text/calendar; charset=utf-8
```

This is the actual sync endpoint.

If a calendar client subscribes to this feed, it can pull calendar updates from Kibegi.

Important distinction:
- `download` gives a file snapshot
- `subscribe` is the endpoint intended for syncing

### 14. Download ICS file

Call:

```http
GET /api/v1/public/schedule/{token}/download/
```

Use this for:
- "Download .ics"
- importing into a calendar manually

## Are the calendars really synced with ICS?

Yes.

What happens is:
- the backend stores events in the database
- the public `subscribe` endpoint converts those events into ICS format
- external calendar apps subscribe to that ICS feed
- when those apps refresh the subscription, they receive updated events

That means this is ICS feed-based sync, not CalDAV.

So the UI should present it as:
- "Subscribe to calendar"
- "Open in calendar app"
- "Download ICS"

Not as:
- "Two-way live sync"

Because external calendar apps consume the Kibegi feed, but they do not push edits back through ICS.

## Frontend Recommendations

### Main schedule screens

Recommended screens:
- schedule home with the 2 default calendars
- calendar detail screen
- event create/edit modal
- share/subscription modal
- public subscription page
- code entry screen

### Good UX patterns

Recommended behavior:
- call `GET /calendars/` on page load
- use `GET /calendars/{id}/` for detail first load
- use `GET /calendars/{id}/events/` after mutations
- keep calendar cards for `classes` and `examination`
- group events by date in the UI
- expose a sync/share button per calendar

### Suggested CTA labels

Use labels like:
- `Subscribe`
- `Open in Calendar App`
- `Copy Feed URL`
- `Download ICS`
- `Show QR Code`
- `Enter Calendar Code`

## Error Handling

Expect these cases:
- `401 Unauthorized` for private endpoints without auth
- `404 Not Found` if the calendar or event does not belong to the user
- `404 Not Found` for public links when `is_public_sync` is false
- `400 Bad Request` for validation errors like invalid times or weekly recurrence without days

Important contract detail:
- successful schedule JSON responses use the project wrapper: `success`, `message`, `data`, `errors`
- serializer validation errors are not wrapped and come back as plain DRF field errors
- some default DRF auth and not-found responses are also not wrapped

Example validation error:

```json
{
  "end_at": ["End time must be after start time."]
}
```

Recommended frontend behavior:
- show field-level validation messages for event form errors
- show a friendly "calendar not available" screen for invalid public links
- show "sync disabled" if public sharing has been turned off

## Important Gotchas

- `GET /api/v1/schedule/events/{eventId}/` exists and is safe to use for event detail screens
- `calendar_id` in the share payload is a string, not a number
- `frontend_subscription_url` can be `null` if `SCHEDULE_FRONTEND_URL` is not configured
- `GET /api/v1/schedule/calendars/{calendarId}/qr/` returns raw `image/png`, not JSON
- `GET /api/v1/schedule/calendars/{calendarId}/share/` still returns URLs even when `is_public_sync` is `false`
- public token/code endpoints only work when `is_public_sync` is `true`
- code lookup is case-insensitive

## Minimal Integration Checklist

- fetch calendars after login
- open one calendar detail
- list events
- create, edit, delete events
- let user rename calendar and toggle `is_public_sync`
- fetch share payload
- expose `webcal_url`, `subscribe_url`, and `download_url`
- optionally render QR code
- build a public subscription page using token or code lookup

## Summary

For the owner:
- manage events through authenticated JSON APIs

For sharing and syncing:
- use the public ICS endpoints

For external calendar apps:
- use `webcal_url` or `subscribe_url`

For manual import:
- use `download_url`
