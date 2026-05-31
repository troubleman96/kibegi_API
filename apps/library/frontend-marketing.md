## Library — Frontend Handoff

Purpose
- Public campus library where users can upload sharable resources (past papers, notes, books) that do NOT count against user storage quotas.

Base routes (all under `/api/v1/library/`)
- `GET /categories/` — list library categories (public)
- `GET /items/` — list public library items (public)
- `GET /items/?category=<slug>&q=<term>&page=<n>` — filtered search (public)
- `GET /items/<code>/` — item detail (public)
- `GET /items/<code>/download/` — download the file (public)
- `POST /items/` — upload a new library item (authenticated)
- `PUT /items/<code>/` or `PATCH` — edit item metadata (authenticated, owner-only)
- `DELETE /items/<code>/` — remove item (authenticated, owner-only)

Response envelope
- All responses follow the project envelope: `{ "success": bool, "data": ..., "message": str }` for successes and `{ "success": false, "error": {"code":..., "message":...} }` for errors.

Item fields (upload / create)
- `title` (string, required)
- `description` (string, optional)
- `file` (file, required) — multipart file upload field
- `file_type` (string, optional) — e.g. `pdf`, `doc`, `image`, `video`, `archive` (frontend should allow free text but validate common types)
- `subject` (string, optional)
- `course_code` (string, optional)
- `author_name` (string, optional)
- `category` (string slug, required) — use slugs from `/categories/`
- `cover_image` (file, optional) — thumbnail or cover image
- `tags` (array of strings, optional)

Item object (example `data` in detail/list responses)
```
{
  "code": "AB12CD",
  "title": "Linear Algebra — Past Paper 2021",
  "description": "Exam paper with solutions",
  "category": { "name": "Past Papers", "slug": "past-papers" },
  "file_url": "https://.../media/library/AB12CD/paper.pdf",
  "thumbnail_url": "https://.../media/library/AB12CD/cover.jpg",
  "download_url": "https://.../api/v1/library/items/AB12CD/download/",
  "file_type": "pdf",
  "uploader": { "id": 23, "name": "Jane Student", "email": "jane@example.com" },
  "created_at": "2026-05-01T12:34:56Z"
}
```

Auth rules
- Browsing endpoints (`GET`) are public — no auth required.
- Upload/edit/delete require JWT authentication (`Authorization: Bearer <token>`).
- Ownership: edits and deletes are restricted to the uploader (server enforces this).

Upload notes (frontend)
- Use `multipart/form-data` for uploads. Field names: `file`, `cover_image`, and the rest as form fields.
- Example curl (upload):
```
curl -X POST "https://<host>/api/v1/library/items/" \
  -H "Authorization: Bearer <JWT>" \
  -F "title=Past Paper 2021" \
  -F "category=past-papers" \
  -F "file=@./paper.pdf;type=application/pdf" \
  -F "cover_image=@./cover.jpg;type=image/jpeg"
```

Download / streaming
- `GET /items/<code>/download/` returns a redirect or direct file stream (server handles Content-Type). Frontend should follow redirects and stream/save appropriately.

Pagination & filtering
- Listing responses use the project envelope and standard pagination. Use `?page=` to iterate. Filtering by `category` (slug) and `q` (search term) supported.

Errors
- Common error shapes:
  - 400 validation: `{ "success": false, "error": {"code": 400, "message": "field: error" } }`
  - 401 unauthorized: `{ "success": false, "error": {"code": 401, "message": "Authentication credentials were not provided." } }`
  - 403 forbidden: `{ "success": false, "error": {"code": 403, "message": "Not allowed." } }`

UX suggestions
- Show `file_type` icon based on MIME or `file_type` field.
- Offer category autocomplete using `/categories/`.
- Preview images/videos inline; for other files show filename and download action.
- For large files show upload progress and allow chunking if needed (backend currently accepts whole files).

Testing notes for frontend QA
- Verify anonymous browsing of `/categories/` and `/items/` (no auth).
- Verify authenticated upload with a valid JWT and that the returned `data` contains `download_url` and `file_url`.
- Verify that a non-owner cannot edit/delete an item (expect 403).

File: `apps/library/frontend-marketing.md`
