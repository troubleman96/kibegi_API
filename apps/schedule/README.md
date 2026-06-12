# Schedule App

This app powers the Kibegi student schedule experience. It combines calendar management, ICS feeds, QR handoff, SMS reminders, and email reminders in one backend area.

What the app does:

- creates 2 default calendars per user: `classes` and `examination`
- stores user-owned class and exam events
- exposes public ICS subscribe/download feeds for calendar clients
- generates QR codes that point users to subscription links
- supports a reminder SMS wallet with SendAfrica credits
- sends reminder email messages for scheduled events
- records public feed access for basic observability

## Folder Map

- [apps/schedule/models.py](models.py) defines calendars, events, public access logs, and SMS wallet/delivery models.
- [apps/schedule/serializers.py](serializers.py) defines the API payloads for calendars, events, share payloads, and SMS wallets.
- [apps/schedule/views.py](views.py) exposes authenticated and public API endpoints.
- [apps/schedule/services.py](services.py) contains ICS generation, QR generation, SMS/email dispatch, and reminder scanning.
- [apps/schedule/urls.py](urls.py) mounts the authenticated routes.
- [apps/schedule/public_urls.py](public_urls.py) mounts the public feed routes.
- [apps/schedule/management/commands/send_schedule_sms_reminders.py](management/commands/send_schedule_sms_reminders.py) is the cron-friendly SMS runner.
- [apps/schedule/tests.py](tests.py) covers the API contract and the SMS reminder path.

## Route Bases

- Authenticated base: `/api/v1/schedule/`
- Public base: `/api/v1/public/schedule/`

## Core Data Model

### `ScheduleCalendar`

Every user gets exactly two calendars:

- `classes`
- `examination`

Important fields:

- `owner` is the logged-in user
- `calendar_type` is read-only and unique per user
- `calendar_code` is a short lookup code used for code-based sharing
- `share_token` is a long public token used for subscribe/download URLs
- `is_public_sync` controls whether the public feed endpoints resolve

### `ScheduleEvent`

Events live inside a calendar.

Important fields:

- `title`, `description`, `location`
- `start_at`, `end_at`
- `event_type`: `class`, `exam`, `study`, `deadline`, `meeting`, `other`
- `recurrence`: `none`, `daily`, `weekly`, `monthly`
- `days` for weekly recurrence
- `reminder_minutes` for the ICS alarm and reminder hint
- `source` marks whether the event came from manual entry, import, or system creation

Validation:

- `end_at` must be after `start_at`
- weekly recurrence must include at least one weekday in `days`

### SMS Models

The SMS reminder feature adds two schedule-owned models:

- `ScheduleSmsAccount` stores the reminder phone number, credit balance, provider metadata, and activation status.
- `ScheduleSmsDeliveryLog` stores each reminder attempt, provider response, credits used, and status.

The reminder wallet is intentionally separate from personal storage and upload quotas.

## Response Shapes

Most schedule endpoints wrap success responses using the project envelope:

```json
{
  "success": true,
  "message": "Schedule calendars retrieved successfully",
  "data": [],
  "errors": null
}
```

Validation errors coming from serializer-backed endpoints are usually plain DRF errors instead of the wrapper.

Example:

```json
{
  "end_at": ["End time must be after start time."]
}
```

## API Surface

### Authenticated Calendar Endpoints

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

### SMS Wallet Endpoints

- `GET /api/v1/schedule/sms-account/`
- `PATCH /api/v1/schedule/sms-account/`

Use the SMS wallet to store the destination phone number and keep the balance of purchased reminder credits.

### Public Feed Endpoints

- `GET /api/v1/public/schedule/{token}/subscribe/`
- `GET /api/v1/public/schedule/{token}/download/`
- `GET /api/v1/public/schedule/{token}/info/`
- `GET /api/v1/public/schedule/code/{code}/info/`

## Public Sharing Flow

When a user opens the share endpoint, the backend returns everything the frontend needs for sharing:

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

- `calendar_id` is returned as a string
- `frontend_subscription_url` is `null` when `SCHEDULE_FRONTEND_URL` is not set
- public token and code endpoints only resolve when `is_public_sync = true`
- the QR endpoint prefers the frontend subscription URL, then falls back to the public info URL

## ICS Details

The ICS feed is generated from stored events and is intended for calendar clients such as Apple Calendar, Outlook, and Google Calendar.

Behaviour:

- `subscribe` returns `text/calendar` inline
- `download` returns `text/calendar` as an attachment
- each stored event becomes one `VEVENT`
- recurrence is translated into `RRULE`
- `reminder_minutes` becomes a `VALARM` block

## SMS Reminder System

The SMS feature is built around three ideas:

1. a user stores one phone number in their schedule SMS wallet
2. reminder messages cost credits, not raw airtime from the user profile
3. a management command scans due events and sends the reminder through the configured SMS provider

The runner command is:

```bash
./.venv/bin/python manage.py send_schedule_sms_reminders
```

The command also supports:

- `--limit N` to process only a few reminders
- `--dry-run` to preview the run without consuming credits or calling the provider

The reminder message is built from:

- event title
- localised start date/time
- optional location

Credits are consumed only after the provider call succeeds. If the account is inactive, the phone number is missing, or the balance is too low, the delivery is marked as skipped.

## Environment Variables

Frontend and SMS-related settings live in the environment.

```env
SCHEDULE_FRONTEND_URL=https://app.kibegi.com/schedule
SEND_AFRICA_API_URL=https://sendafrica.online/api
SEND_AFRICA_USERNAME=
SEND_AFRICA_API_KEY=
SEND_AFRICA_SENDER_ID=
SCHEDULE_SMS_COST_PER_MESSAGE=1
SCHEDULE_SMS_GRACE_MINUTES=10
SCHEDULE_SMS_LOOKAHEAD_DAYS=7
```

What they do:

- `SCHEDULE_FRONTEND_URL` builds the front-end subscription URL used by QR and share responses
- `SEND_AFRICA_USERNAME` and `SEND_AFRICA_API_KEY` authenticate provider calls
- `SEND_AFRICA_SENDER_ID` is optional and used when the provider account allows it
- `SCHEDULE_SMS_COST_PER_MESSAGE` defines how many credits one reminder consumes
- `SCHEDULE_SMS_GRACE_MINUTES` defines the acceptable send window around the reminder time
- `SCHEDULE_SMS_LOOKAHEAD_DAYS` limits how far ahead the reminder scanner looks

## SMS Credit Model

The SMS wallet is intentionally independent from the personal storage system.

Current behaviour:

- the wallet belongs to the authenticated schedule owner
- credits are tracked in `balance_credits`
- each reminder consumes one credit by default
- the provider response is saved in the delivery log when sending succeeds
- the admin can inspect phone number, balance, and delivery history

This design makes it easy to sell credits separately, top up in bundles, and audit every reminder that was sent.

## Cron / Scheduler Setup

Run the reminder command every minute from cron or your host scheduler.

Example Linux cron entry:

```cron
* * * * * cd /home/cameltech/Projects/KiBEGI/API && ./.venv/bin/python manage.py send_schedule_sms_reminders >> /home/cameltech/Projects/KiBEGI/API/logs/schedule-sms.log 2>&1
```

If you want to test without sending messages, use:

```bash
./.venv/bin/python manage.py send_schedule_sms_reminders --dry-run
```

## Admin Visibility

The admin includes:

- schedule calendars
- schedule events
- public access logs
- SMS wallets
- SMS delivery logs

That makes it possible to troubleshoot missed reminders without reading raw application logs only.

## Testing Notes

The schedule test slice covers:

- default calendar creation
- calendar list/detail flows
- event create/update/delete flows
- public feed info and ICS downloads
- QR generation
- SMS wallet endpoint behaviour
- reminder dispatch success and insufficient-credit skip handling

Run the focused tests with:

```bash
./.venv/bin/python manage.py test apps.schedule.tests --settings=kibegi_api.test_settings
```

## Integration Notes

- treat the public schedule feeds as ICS feeds, not CalDAV
- call the share endpoint after event mutations if the frontend needs fresh URLs
- use the SMS wallet endpoint to configure the phone number before enabling reminders
- reminders are only as reliable as the scheduler that runs the management command

## Troubleshooting

If reminders do not send:

- confirm the SMS account has a phone number
- confirm `balance_credits > 0`
- confirm SendAfrica credentials are set
- confirm the cron job is running the command on schedule
- confirm the event falls within the reminder window defined by `reminder_minutes` and `SCHEDULE_SMS_GRACE_MINUTES`

If public feeds return `404`:

- confirm `is_public_sync` is enabled for that calendar
- confirm you are using the correct token or short code
- confirm the route is being called under `/api/v1/public/schedule/`

If QR codes do not open the frontend page:

- confirm `SCHEDULE_FRONTEND_URL` is set
- otherwise the QR will point to the backend public info page

## Related Files

- [apps/schedule/SMS_REMINDERS.md](SMS_REMINDERS.md)
- [apps/schedule/FRONTENDUSE.md](FRONTENDUSE.md)
- the reminder command scans due events and consumes 1 credit per message by default
- the host should run `python manage.py send_schedule_sms_reminders` every minute from cron or a scheduler

Example payload to configure a phone number:

```json
{
  "phone_number": "+254700000000",
  "sender_id": "KIBEGI"
}
```

Notes:

- reminders are skipped when the wallet is inactive, the phone number is missing, or credits are exhausted
- reminder attempts are logged in the admin as SMS delivery records
- SendAfrica responses are stored for audit when delivery succeeds

## Integration Notes

- treat this as ICS feed subscription, not CalDAV
- public calendar clients can read updates from Kibegi, but cannot push edits back
- the safest frontend flow after event mutations is to refresh `GET /calendars/{id}/events/` or `GET /calendars/{id}/`
