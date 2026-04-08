# Recent Updates

This file summarizes the latest profile-related backend support that the frontend can rely on.

## User Profile

The authenticated user profile endpoint already supports reading and updating the username.

Endpoint:

```http
GET /api/v1/auth/profile/
PATCH /api/v1/auth/profile/
PUT /api/v1/auth/profile/
```

Auth:

```http
Authorization: Bearer <access_token>
```

Current profile response shape:

```json
{
  "success": true,
  "message": "Success",
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "User Name",
    "user_type": "student",
    "profile_image": "profiles/<id>/profile.png",
    "profile_image_url": "https://.../profiles/<id>/profile.png",
    "date_joined": "2026-04-08T09:00:00Z"
  },
  "errors": null
}
```

To change the displayed username:

```http
PATCH /api/v1/auth/profile/
Content-Type: application/json
```

```json
{
  "username": "New Display Name"
}
```

Notes:

- `username` maps to the backend `full_name` field.
- `email` is read-only here.

## Profile Picture Upload

Users can upload or replace their profile picture through:

```http
POST /api/v1/auth/profile/image/
Content-Type: multipart/form-data
```

Form field:

```text
profile_image
```

Rules:

- Supported formats: JPEG, JPG, PNG, GIF, WebP
- Max size: 5MB
- Minimum dimensions: 50x50
- Maximum dimensions: 2000x2000
- Uploading a new image replaces the old one

Success response returns the updated profile payload, including `profile_image_url`.

## Profile Picture Remove

Users can remove their current picture through:

```http
DELETE /api/v1/auth/profile/image/
```

Success response:

```json
{
  "success": true,
  "message": "Profile image removed successfully",
  "data": null,
  "errors": null
}
```

## Change Password

Authenticated users can change their password through:

```http
POST /api/v1/auth/change-password/
Content-Type: application/json
```

```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword123!",
  "confirm_password": "NewPassword123!"
}
```

Rules:

- `current_password` must match the current password
- `new_password` and `confirm_password` must match
- Django password validation still applies

Success response:

```json
{
  "success": true,
  "message": "Password changed successfully",
  "data": null,
  "errors": null
}
```

## Verification Added

The latest test coverage now explicitly verifies:

- username update through `/api/v1/auth/profile/`
- profile image upload through `/api/v1/auth/profile/image/`
- profile image removal through `/api/v1/auth/profile/image/`
- authenticated password change through `/api/v1/auth/change-password/`

These checks live in:

- [apps/core/test_api_endpoints.py](/home/troubleman/projects/Kibegi/Backend/apps/core/test_api_endpoints.py)

## Redis API Caching

The API now supports Redis-backed response caching for read-heavy endpoints without changing existing response shapes.

Behavior:

- Uses Redis when `REDIS_URL` is set
- Falls back safely to Django local memory cache when Redis is not configured
- Caches only successful JSON `GET` responses for read-heavy endpoints
- Automatically invalidates related cache groups after profile, class, upload, file, friend, share, notification, and storage mutations

Configured endpoint groups:

- profile endpoints
- classes and class search endpoints
- global search endpoint
- uploads list/detail/trash/search/recent endpoints
- files aggregate/detail/deleted endpoints
- friends list/search/request-list endpoints
- notifications list endpoint
- sharing list/detail endpoints
- storage summary/info/history endpoints

Production environment:

```env
REDIS_URL=redis://127.0.0.1:6379/1
```

If Redis is unavailable, the API still works normally and uses local in-process caching instead.
