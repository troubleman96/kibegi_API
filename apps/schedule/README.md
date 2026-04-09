# Schedule App

This app provides a user-owned schedule system for Kibegi with:

- 2 default calendars per user: `classes` and `examination`
- authenticated calendar and event management
- public token-based ICS subscribe/download
- short manual calendar codes
- QR code generation for mobile handoff
- optional frontend subscription page support via `SCHEDULE_FRONTEND_URL`

## Mounted Routes

- Authenticated base: `/api/v1/schedule/`
- Public base: `/api/v1/public/schedule/`

## Authenticated Endpoints

- `GET /api/v1/schedule/calendars/`
- `GET /api/v1/schedule/calendars/{id}/`
- `PATCH /api/v1/schedule/calendars/{id}/`
- `GET /api/v1/schedule/calendars/{id}/events/`
- `POST /api/v1/schedule/calendars/{id}/events/`
- `GET /api/v1/schedule/events/{id}/`
- `PATCH /api/v1/schedule/events/{id}/`
- `DELETE /api/v1/schedule/events/{id}/`
- `GET /api/v1/schedule/calendars/{id}/share/`
- `GET /api/v1/schedule/calendars/{id}/qr/`

## Public Endpoints

- `GET /api/v1/public/schedule/{token}/subscribe/`
- `GET /api/v1/public/schedule/{token}/download/`
- `GET /api/v1/public/schedule/{token}/info/`
- `GET /api/v1/public/schedule/code/{code}/info/`

## Default Calendars

Each user automatically gets exactly 2 calendars:

- `classes`
- `examination`

Users do not create extra calendars through this API. Missing defaults are created:

- automatically for new users
- lazily for existing users when schedule endpoints are accessed

## Response Shapes

Successful JSON responses from schedule endpoints use the project wrapper:

```json
{
  "success": true,
  "message": "Schedule calendars retrieved successfully",
  "data": [],
  "errors": null
}
```

Important error behavior:

- `GET /share/` and public metadata errors use the same wrapped format with `success: false`
- validation errors from serializer-backed endpoints are plain DRF error objects, not wrapped
- auth failures and many default `404` responses from generic views also follow DRF defaults, not the wrapper

Example validation error:

```json
{
  "end_at": ["End time must be after start time."]
}
```

## Calendar Object

Returned by calendar list/detail endpoints:

```json
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
}
```

Notes:

- `calendar_type` is read-only
- `calendar_code` is read-only
- calendar detail adds a read-only `events` array

## Event Object

Returned by event list/detail/create/update endpoints:

```json
{
  "id": 12,
  "calendar": 1,
  "title": "Linear Algebra",
  "description": "Matrices and vectors",
  "location": "Room 4B",
  "start_at": "2026-05-01T09:00:00Z",
  "end_at": "2026-05-01T10:30:00Z",
  "event_type": "class",
  "recurrence": "weekly",
  "days": ["monday", "wednesday"],
  "reminder_minutes": 20,
  "source": "manual",
  "created_at": "2026-04-09T10:00:00Z",
  "updated_at": "2026-04-09T10:00:00Z"
}
```

Write rules:

- do not send `calendar` when creating an event; it is derived from `{calendarId}` in the route
- `calendar`, `source`, `created_at`, and `updated_at` are read-only
- `PATCH` supports partial updates

Supported values:

- `event_type`: `class`, `exam`, `study`, `deadline`, `meeting`, `other`
- `recurrence`: `none`, `daily`, `weekly`, `monthly`

Validation rules:

- `end_at` must be after `start_at`
- if `recurrence` is `weekly`, `days` must contain at least one weekday

## Share Payload

`GET /api/v1/schedule/calendars/{id}/share/`

Example response data:

```json
{
  "calendar_id": "1",
  "calendar_type": "classes",
  "calendar_code": "AB7K9Q",
  "subscribe_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/subscribe/",
  "download_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/download/",
  "webcal_url": "webcal://api.kibegi.com/api/v1/public/schedule/<token>/subscribe/",
  "subscription_page_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/info/",
  "frontend_subscription_url": "https://app.kibegi.com/schedule/subscribe/<token>",
  "code_lookup_url": "https://api.kibegi.com/api/v1/public/schedule/code/AB7K9Q/info/"
}
```

Notes:

- `calendar_id` is returned as a string, not a number
- `frontend_subscription_url` is `null` when `SCHEDULE_FRONTEND_URL` is not configured
- share URLs are returned even when `is_public_sync` is `false`
- if `is_public_sync` is `false`, the public token/code endpoints will still return `404`

## QR Endpoint

`GET /api/v1/schedule/calendars/{id}/qr/`

Behavior:

- returns raw PNG bytes, not JSON
- `Content-Type` is `image/png`
- QR target is `frontend_subscription_url` when configured, otherwise `subscription_page_url`
- the QR endpoint itself does not check `is_public_sync`

## Public Metadata Payload

Returned by:

- `GET /api/v1/public/schedule/{token}/info/`
- `GET /api/v1/public/schedule/code/{code}/info/`

Example response data:

```json
{
  "name": "My Classes",
  "calendar_type": "classes",
  "description": "Default classes schedule for John Doe.",
  "calendar_code": "AB7K9Q",
  "event_count": 2,
  "subscribe_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/subscribe/",
  "download_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/download/",
  "webcal_url": "webcal://api.kibegi.com/api/v1/public/schedule/<token>/subscribe/",
  "subscription_page_url": "https://api.kibegi.com/api/v1/public/schedule/<token>/info/",
  "frontend_subscription_url": "https://app.kibegi.com/schedule/subscribe/<token>"
}
```

Notes:

- code lookup is case-insensitive
- public endpoints only resolve calendars where `is_public_sync = true`

## ICS Endpoints

`GET /api/v1/public/schedule/{token}/subscribe/`

- returns `text/calendar; charset=utf-8`
- `Content-Disposition` is `inline`
- intended for live calendar subscription

`GET /api/v1/public/schedule/{token}/download/`

- returns `text/calendar; charset=utf-8`
- `Content-Disposition` is `attachment`
- intended for manual `.ics` download/import

The ICS feed contains:

- one `VEVENT` per stored schedule event
- optional `RRULE` values for `daily`, `weekly`, and `monthly`
- optional `VALARM` when `reminder_minutes` is set

## Frontend Configuration

Set:

```env
SCHEDULE_FRONTEND_URL=https://app.kibegi.com/schedule
```

When configured, the backend builds:

- `frontend_subscription_url = https://app.kibegi.com/schedule/subscribe/{share_token}`

## Integration Notes

- treat this as ICS feed subscription, not CalDAV
- public calendar clients can read updates from Kibegi, but cannot push edits back
- the safest frontend flow after event mutations is to refresh `GET /calendars/{id}/events/` or `GET /calendars/{id}/`
