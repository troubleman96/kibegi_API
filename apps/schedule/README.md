# Schedule App

This app provides a user-owned schedule system for Kibegi with:

- 2 default calendars per user: `classes` and `examination`
- authenticated event management
- public token-based ICS subscribe/download
- short manual calendar codes
- QR code generation for mobile handoff
- optional frontend subscription page support via `SCHEDULE_FRONTEND_URL`

## Main Endpoints

Authenticated:

- `GET /api/v1/schedule/calendars/`
- `GET /api/v1/schedule/calendars/{id}/`
- `PATCH /api/v1/schedule/calendars/{id}/`
- `GET /api/v1/schedule/calendars/{id}/events/`
- `POST /api/v1/schedule/calendars/{id}/events/`
- `PATCH /api/v1/schedule/events/{id}/`
- `DELETE /api/v1/schedule/events/{id}/`
- `GET /api/v1/schedule/calendars/{id}/share/`
- `GET /api/v1/schedule/calendars/{id}/qr/`

Public:

- `GET /api/v1/public/schedule/{token}/subscribe/`
- `GET /api/v1/public/schedule/{token}/download/`
- `GET /api/v1/public/schedule/{token}/info/`
- `GET /api/v1/public/schedule/code/{code}/info/`

## Frontend URL

Set:

```env
SCHEDULE_FRONTEND_URL=https://app.kibegi.com/schedule
```

When this is configured, the share payload includes:

- `frontend_subscription_url`

Example:

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

## Notes

- Default calendars are created automatically for new users by signal.
- Existing users also get missing default calendars lazily when they first hit schedule endpoints.
- Public subscribe/download endpoints only work for calendars with `is_public_sync=true`.
