# Classes API

This document explains the `classes` app endpoints as they work right now in the backend.

Base path:

```text
/api/v1/classes/
```

Auth:
z
- All endpoints in this app require an authenticated user.
- Use the normal Bearer token header:

```http
Authorization: Bearer <access_token>
```

Response style:

- Most non-paginated endpoints return the shared API format:

```json
{
  "success": true,
  "message": "Human readable message",
  "data": {},
  "errors": null
}
```

- Paginated list endpoints return DRF pagination fields at the top level:

```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": []
}
```

## 1. List My Classes

Endpoint:

```http
GET /api/v1/classes/
```

What it does:

- Returns classes where the current user is already a member.
- This endpoint does not return all public classes.
- Use the search endpoint to discover other classes.

Response item shape:

```json
{
  "id": "uuid",
  "name": "Algorithms",
  "class_code": "ABC123",
  "is_public": false,
  "is_verified": true,
  "creator_name": "Lecturer User",
  "creator_type": "lecturer",
  "member_count": 18,
  "created_at": "2026-04-08T09:00:00Z"
}
```

Suggested page usage:

- Main classes page for "My Classes"
- Empty state when `results` is empty
- Card click should go to class detail page

## 2. Create Class

Endpoint:

```http
POST /api/v1/classes/
```

Request body:

```json
{
  "name": "Algorithms",
  "description": "Class for data structures and algorithms",
  "is_public": false
}
```

Notes:

- `creator` is assigned automatically from the logged-in user.
- `class_code` is generated automatically.
- `is_verified` is automatic:
  - `true` for lecturer-created classes
  - `false` for student-created classes
- The creator is automatically added as a member.
- Creator role is automatic:
  - lecturer creator -> `lecturer`
  - student creator -> `student`

Success response data shape:

```json
{
  "id": "uuid",
  "name": "Algorithms",
  "description": "Class for data structures and algorithms",
  "class_code": "ABC123",
  "is_public": false,
  "is_verified": true,
  "creator": 1,
  "creator_name": "Lecturer User",
  "creator_type": "lecturer",
  "member_count": 1,
  "is_member": true,
  "user_role": "lecturer",
  "created_at": "2026-04-08T09:00:00Z",
  "updated_at": "2026-04-08T09:00:00Z"
}
```

Suggested page usage:

- "Create class" form
- After success, route user to class detail page and surface the `class_code`

## 3. Search Classes

Endpoint:

```http
GET /api/v1/classes/search/?q=algo
```

What it does:

- Searches by:
  - class name
  - class code
- Returns classes that are:
  - public, or
  - already joined by the current user

Response item shape:

```json
{
  "id": "uuid",
  "name": "Algorithms",
  "class_code": "ABC123",
  "is_public": false,
  "is_verified": true,
  "creator_name": "Lecturer User",
  "creator_type": "lecturer",
  "member_count": 18,
  "created_at": "2026-04-08T09:00:00Z"
}
```

Suggested page usage:

- Search/discovery page
- Join CTA for classes the user is not yet a member of

## 4. Join Class

Endpoint:

```http
POST /api/v1/classes/join/
```

Request body:

```json
{
  "class_code": "ABC123"
}
```

What it does:

- Joins the class using the class code.
- New joined users are added with role `student`.

Success response data shape:

```json
{
  "id": "uuid",
  "name": "Algorithms",
  "description": "Class for data structures and algorithms",
  "class_code": "ABC123",
  "is_public": false,
  "is_verified": true,
  "creator": 1,
  "creator_name": "Lecturer User",
  "creator_type": "lecturer",
  "member_count": 18,
  "is_member": true,
  "user_role": "student",
  "created_at": "2026-04-08T09:00:00Z",
  "updated_at": "2026-04-08T09:00:00Z"
}
```

Common error cases:

- `400` invalid class code
- `400` already a member

## 5. Get Class Detail

Endpoint:

```http
GET /api/v1/classes/<class_id>/
```

Access rules:

- Allowed if the user is a class member
- Allowed if the class is public
- Otherwise returns `403`

This is the richest endpoint in the app and should power the class detail page.

Response data shape:

```json
{
  "id": "uuid",
  "name": "Algorithms",
  "description": "Class for data structures and algorithms",
  "class_code": "ABC123",
  "is_public": false,
  "is_verified": true,
  "creator": 1,
  "creator_name": "Lecturer User",
  "creator_type": "lecturer",
  "member_count": 18,
  "is_member": true,
  "user_role": "student",
  "created_at": "2026-04-08T09:00:00Z",
  "updated_at": "2026-04-08T09:00:00Z",
  "uploads_summary": {
    "total_uploads": 12,
    "uploads_by_type": {
      "document": 8,
      "image": 2,
      "presentation": 2
    },
    "total_size_bytes": 10485760,
    "total_size_mb": 10.0,
    "lecturers_with_uploads": 1,
    "active_contributors": 2
  },
  "recent_uploads": [
    {
      "id": "uuid",
      "file_name": "lecture1.pdf",
      "file_type": "document",
      "file_size": 1200000,
      "file_code": "FILE1234",
      "uploader_id": "uuid",
      "uploader_name": "Lecturer User",
      "uploader_type": "lecturer",
      "created_at": "2026-04-08T09:00:00Z"
    }
  ],
  "uploader_stats": [
    {
      "uploader_id": "uuid",
      "uploader_name": "Lecturer User",
      "uploader_type": "lecturer",
      "upload_count": 7,
      "is_active_contributor": true
    }
  ]
}
```

Suggested page sections:

- Class header:
  - `name`
  - `description`
  - `class_code`
  - public/private badge
  - verified/study-group badge
- Summary cards:
  - member count
  - total uploads
  - total size
  - lecturers with uploads
- Recent uploads list
- Contributors / uploader stats

## 6. Update Class

Endpoints:

```http
PATCH /api/v1/classes/<class_id>/
PUT /api/v1/classes/<class_id>/
```

Who can update:

- Only the class creator

Allowed fields to send:

```json
{
  "name": "New name",
  "description": "Updated description",
  "is_public": true
}
```

Notes:

- Do not send server-managed fields like:
  - `id`
  - `class_code`
  - `creator`
  - `is_verified`
  - `created_at`
  - `updated_at`

Success response data shape:

- Same base class shape as create response, without uploads summary fields.

Common error cases:

- `403` if current user is not the creator

## 7. Delete Class

Endpoint:

```http
DELETE /api/v1/classes/<class_id>/
```

Who can delete:

- Only the class creator

Success response:

```json
{
  "success": true,
  "message": "Class deleted successfully",
  "data": null,
  "errors": null
}
```

Common error cases:

- `403` if current user is not the creator

## 8. List Class Members

Endpoint:

```http
GET /api/v1/classes/<class_id>/members/
```

Access rules:

- Allowed if the user is a class member
- Allowed if the class is public
- Otherwise `403`

Response item shape:

```json
{
  "id": "uuid",
  "full_name": "Student User",
  "email": "student@test.com",
  "user_type": "student",
  "role": "student",
  "joined_at": "2026-04-08T09:00:00Z"
}
```

Suggested page usage:

- Members tab
- Show role badge
- Separate lecturer vs student visually using `user_type` or `role`

## 9. Leave Class

Endpoint:

```http
POST /api/v1/classes/<class_id>/leave/
```

What it does:

- Removes the current user’s membership from the class.

Rules:

- Class creator cannot leave their own class
- User must already be a member

Success response:

```json
{
  "success": true,
  "message": "Successfully left the class",
  "data": null,
  "errors": null
}
```

Common error cases:

- `404` class not found
- `400` class creator cannot leave
- `400` user is not a member

## UI Mapping Suggestion

If the classes page is missing, this is a safe page split:

1. My Classes page
   Use `GET /api/v1/classes/`

2. Explore / Search Classes page
   Use `GET /api/v1/classes/search/?q=...`

3. Create Class page/modal
   Use `POST /api/v1/classes/`

4. Join by Code modal
   Use `POST /api/v1/classes/join/`

5. Class Detail page
   Use `GET /api/v1/classes/<id>/`

6. Members tab
   Use `GET /api/v1/classes/<id>/members/`

7. Settings actions
   Use:
   - `PATCH /api/v1/classes/<id>/`
   - `DELETE /api/v1/classes/<id>/`
   - `POST /api/v1/classes/<id>/leave/`

## Important Behavior Notes

- `GET /api/v1/classes/` is for joined classes, not all discoverable classes.
- Public class discovery should use search.
- `is_verified` is not a manual input from the client.
- Student-created classes become study groups with `is_verified = false`.
- Lecturer-created classes become verified classes with `is_verified = true`.
- Joining always gives role `student`.
- Only creators can edit or delete classes.
- The detail endpoint is the best source for building the class dashboard page.
