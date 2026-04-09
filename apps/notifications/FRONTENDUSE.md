# Notifications (Frontend Integration)

The backend currently supports **polling-based** notifications (no WebSocket push).

## Fast polling endpoint (recommended for UI badges/toasts)

- `GET /api/v1/notifications/unread-count/` (authenticated)

Response:

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": { "unread_count": 3 },
  "errors": null
}
```

### Suggested UI behavior ("popping")

1. Poll `unread-count` every 10–30 seconds (and also on app focus).
2. If `unread_count` increased since last poll, show a toast/snackbar like:
   - "You have new notifications" + button "View"
3. When opening the notifications screen, fetch the full list and render newest first:
   - `GET /api/v1/notifications/?is_read=all`

## Listing notifications

- `GET /api/v1/notifications/` supports:
  - `?is_read=true|false|all` (default `all`)
  - `?type=<notification_type>`

## Marking as read

- `POST /api/v1/notifications/{id}/read/`
- `POST /api/v1/notifications/read-all/`

## Notification types you can expect

- `share_request` (someone shared a file with you)
- `share_accepted` / `share_rejected` (your share was accepted/rejected)
- `friend_request` / `friend_accepted`
- `upload_created` (new upload in a class you joined)
- `class_joined` (someone joined your class)

## Performance note

If `REDIS_URL` is configured on the backend, notification list + unread count are cached for faster responses.
