# Profile Picture (Frontend Guide)

This backend stores user profile pictures in `User.profile_image` and exposes a stable URL for the frontend to render.

## Where to get the URL

Use the `profile_image_url` field returned by these endpoints:

- `POST /api/v1/auth/login/` → `data.user.profile_image_url`
- `POST /api/v1/auth/register/verify/` → `data.user.profile_image_url`
- `GET /api/v1/auth/profile/` → `data.profile_image_url`
- `POST /api/v1/auth/profile/image/` (upload) → `data.profile_image_url`

If the user has no picture, `profile_image_url` is `null`.

## Rendering rule (recommended)

- Prefer `profile_image_url` when present.
- Fallback to a local placeholder avatar when it is `null`.
- Ignore `profile_image` unless you need debugging; it may be a relative path.

### Example (React)

```ts
const avatarSrc = user.profile_image_url ?? "/assets/avatar-placeholder.png";
```

## Uploading / updating the profile picture

Endpoint:

- `POST /api/v1/auth/profile/image/` (authenticated)

Request:

- `multipart/form-data` with field name `profile_image`

Example (fetch):

```ts
const form = new FormData();
form.append("profile_image", file);

const res = await fetch(`${API_BASE_URL}/api/v1/auth/profile/image/`, {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: form,
});
const json = await res.json();
const profileImageUrl = json?.data?.profile_image_url ?? null;
```

## If you ever receive a relative URL

Most clients should receive an absolute `profile_image_url`. If an older endpoint returns a relative value like `/media/...`, build an absolute URL using the backend origin:

```ts
function toAbsoluteUrl(url: string, apiBaseUrl: string) {
  if (!url) return url;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return new URL(url, apiBaseUrl).toString();
}
```

## Notes

- In development, Django serves media under `/media/` when `DEBUG=true`.
- In production, media URLs may point to MinIO/S3 (depending on `MINIO_PUBLIC_BASE_URL` and storage settings).
