# Files App API Documentation

## Overview

The **Files App** provides a unified view of all file-related content across the platform. It aggregates files from both the **Uploads** and **Sharing** apps, making it easier to manage all your files in one place.

### Key Features

- 📁 **Unified View**: See all your files (uploads + shared) in one place
- 🔍 **Single File Lookup**: Get details about any file by file_code
- 📤 **My Uploads**: View only files you've uploaded
- 📥 **Shared With Me**: View only files shared with you
- 🗑️ **Deleted Files**: Track all deleted files from both uploads and sharing
- ⏰ **Retention Info**: See days remaining before permanent deletion

---

## Base URL

```
/api/v1/files/
```

---

## Endpoints

### Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/all/` | Get all files (uploads + shared) |
| GET | `/my-uploads/` | Get only your uploads |
| GET | `/shared-with-me/` | Get only shared files |
| GET | `/deleted/` | Get deleted files (trash) |
| GET | `/{file_code}/` | Get single file details |
| POST | `/{file_code}/restore/` | Restore file from trash |
| DELETE | `/{file_code}/permanent-delete/` | Permanently delete file |

---

### 1. Get All Files

**Endpoint:** `GET /api/v1/files/all/`

**Authentication:** Required

**Description:** Returns all files available to the user - both uploaded files and accepted shared files (excluding deleted files).

**Response (200):**
```json
{
  "success": true,
  "message": "Retrieved 15 files",
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "file_code": "ABC123",
      "file_name": "report.pdf",
      "file_size": 2048576,
      "file_type": "application/pdf",
      "file_url": "http://example.com/media/uploads/user_id/report.pdf",
      "source": "upload",
      "owner": {
        "id": "user-uuid",
        "username": "john_doe",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe"
      },
      "uploaded_at": "2024-01-15T10:30:00Z",
      "is_deleted": false,
      "deleted_at": null,
      "shared_by": null,
      "shared_at": null,
      "accepted": null
    },
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "file_code": "XYZ789",
      "file_name": "presentation.pptx",
      "file_size": 5242880,
      "file_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "file_url": "http://example.com/media/uploads/other_user/presentation.pptx",
      "source": "shared",
      "owner": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "uploaded_at": "2024-01-10T08:00:00Z",
      "is_deleted": false,
      "deleted_at": null,
      "shared_by": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "shared_at": "2024-01-12T14:30:00Z",
      "accepted": true
    }
  ]
}
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Either "upload" (your file) or "shared" (shared with you) |
| `owner` | object | The original uploader of the file (contains: id, email, full_name, user_type) |
| `shared_by` | object | Who shared the file (null for uploads; contains: id, email, full_name, user_type) |
| `shared_at` | datetime | When file was shared (null for uploads) |
| `accepted` | boolean | Share acceptance status (null for uploads) |

**Note:** User objects contain: `id` (UUID), `email` (string), `full_name` (string), `user_type` (string: "student" or "lecturer")

---

### 2. Get My Uploads

**Endpoint:** `GET /api/v1/files/my-uploads/`

**Authentication:** Required

**Description:** Returns only files uploaded by the authenticated user (excluding deleted files).

**Response (200):**
```json
{
  "success": true,
  "message": "Retrieved 8 uploads",
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "file_code": "ABC123",
      "file_name": "report.pdf",
      "file_size": 2048576,
      "file_type": "application/pdf",
      "file_url": "http://example.com/media/uploads/user_id/report.pdf",
      "source": "upload",
      "owner": {
        "id": "user-uuid",
        "username": "john_doe",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe"
      },
      "uploaded_at": "2024-01-15T10:30:00Z",
      "is_deleted": false,
      "deleted_at": null,
      "shared_by": null,
      "shared_at": null,
      "accepted": null
    }
  ]
}
```

---

### 3. Get Files Shared With Me

**Endpoint:** `GET /api/v1/files/shared-with-me/`

**Authentication:** Required

**Description:** Returns only files that have been shared with the authenticated user (accepted only, excluding deleted files).

**Response (200):**
```json
{
  "success": true,
  "message": "Retrieved 7 shared files",
  "data": [
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "file_code": "XYZ789",
      "file_name": "presentation.pptx",
      "file_size": 5242880,
      "file_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "file_url": "http://example.com/media/uploads/other_user/presentation.pptx",
      "source": "shared",
      "owner": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "uploaded_at": "2024-01-10T08:00:00Z",
      "is_deleted": false,
      "deleted_at": null,
      "shared_by": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "shared_at": "2024-01-12T14:30:00Z",
      "accepted": true
    }
  ]
}
```

---

### 4. Get Deleted Files

**Endpoint:** `GET /api/v1/files/deleted/`

**Authentication:** Required

**Description:** Returns all deleted files from both uploads and sharing. Shows files in trash that can still be restored within the 21-day retention period.

**Response (200):**
```json
{
  "success": true,
  "message": "Retrieved 5 deleted files",
  "data": [
    {
      "id": "323e4567-e89b-12d3-a456-426614174002",
      "file_code": "DEL001",
      "file_name": "old_document.docx",
      "file_size": 1048576,
      "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "source": "upload",
      "owner": {
        "id": "user-uuid",
        "username": "john_doe",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe"
      },
      "deleted_at": "2024-01-20T15:00:00Z",
      "days_until_permanent_deletion": 18,
      "shared_by": null,
      "was_accepted": null
    },
    {
      "id": "423e4567-e89b-12d3-a456-426614174003",
      "file_code": "DEL002",
      "file_name": "shared_image.jpg",
      "file_size": 3145728,
      "file_type": "image/jpeg",
      "source": "shared",
      "owner": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "deleted_at": "2024-01-18T12:00:00Z",
      "days_until_permanent_deletion": 16,
      "shared_by": {
        "id": "owner-uuid",
        "username": "jane_smith",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "was_accepted": true
    }
  ]
}
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `days_until_permanent_deletion` | integer | Days remaining before file is permanently deleted (0-21) |
| `was_accepted` | boolean | For shared files: whether share was accepted before deletion |

**Notes:**
- Files are automatically deleted after 21 days in trash
- Use restore endpoints in uploads/sharing apps to recover files
- Use permanent delete endpoints to immediately delete files

---

### 5. Get Single File Details

**Endpoint:** `GET /api/v1/files/{file_code}/`

**Authentication:** Required

**Description:** Returns detailed information about a specific file. Searches in both uploads and shared files.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_code` | string | Unique file code (e.g., "ABC123") |

**Success Response (200):**
```json
{
  "success": true,
  "message": "File found in uploads",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "file_code": "ABC123",
    "file_name": "report.pdf",
    "file_size": 2048576,
    "file_type": "application/pdf",
    "file_url": "http://example.com/media/uploads/user_id/report.pdf",
    "source": "upload",
    "owner": {
      "id": "user-uuid",
      "email": "john@example.com",
      "full_name": "John Doe",
      "user_type": "student"
    },
    "uploaded_at": "2024-01-15T10:30:00Z",
    "is_deleted": false,
    "deleted_at": null,
    "shared_by": null,
    "shared_at": null,
    "accepted": null
  }
}
```

**Error Response (404):**
```json
{
  "success": false,
  "message": "File not found"
}
```

---

### 6. Restore File from Trash

**Endpoint:** `POST /api/v1/files/{file_code}/restore/`

**Authentication:** Required

**Description:** Restore a deleted file from trash by file_code. Only works for your uploads (shared files don't have trash).

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_code` | string | Unique file code (e.g., "ABC123") |

**Behavior:**

- **For Your Uploads:**
  - File must be in trash (soft deleted)
  - Restores the file (reverses soft delete)
  - File becomes accessible again
  - Can be downloaded, shared, etc.

- **For Shared Files:**
  - Not applicable (shared files don't use trash)
  - Returns 404

**Success Response (200):**

```json
{
  "success": true,
  "message": "'document.pdf' restored successfully",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "file_code": "ABC123",
    "file_name": "document.pdf",
    "file_size": 2048576,
    "file_type": "application/pdf",
    "file_url": "http://example.com/media/uploads/user_id/document.pdf",
    "source": "upload",
    "owner": {
      "id": "user-uuid",
      "email": "john@example.com",
      "full_name": "John Doe",
      "user_type": "student"
    },
    "uploaded_at": "2024-01-15T10:30:00Z",
    "is_deleted": false,
    "deleted_at": null,
    "shared_by": null,
    "shared_at": null,
    "accepted": null
  }
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `401` | Not authenticated |
| `404` | File not found in trash or not an upload |

**Important Notes:**

- ✅ Only works for YOUR uploads
- ✅ File must be in trash first
- ✅ Reverses soft delete (sets is_deleted=False, deleted_at=None)
- ✅ File immediately becomes accessible
- ❌ Cannot restore shared files (they don't have trash)

**Example Usage:**

```bash
# Restore your uploaded file from trash
curl -X POST http://localhost:8000/api/v1/files/ABC123/restore/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### 7. Permanently Delete File

**Endpoint:** `DELETE /api/v1/files/{file_code}/permanent-delete/`

**Authentication:** Required

**Description:** Permanently delete a file by file_code. Handles both uploads and shared files intelligently.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_code` | string | Unique file code (e.g., "ABC123") |

**Behavior:**

1. **For Your Uploads:**
   - File must be in trash (soft deleted first)
   - Permanently deletes physical file from storage
   - Removes database record
   - ⚠️ **WARNING: This is irreversible!**

2. **For Shared Files:**
   - Removes the shared file from your view
   - Original file remains with the owner
   - Can be re-shared by owner if needed

**Success Response (200):**

For uploads:
```json
{
  "success": true,
  "message": "'document.pdf' permanently deleted"
}
```

For shared files:
```json
{
  "success": true,
  "message": "'presentation.pptx' removed from your files"
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `401` | Not authenticated |
| `404` | File not found or not in trash (for uploads) |

**Important Notes:**

- ✅ Works with file_code (no need to track UUIDs)
- ✅ Automatically determines if file is upload or shared
- ✅ For uploads: Must be in trash first (soft delete required)
- ✅ For shared files: No trash requirement, immediate removal
- ⚠️ Uploads are permanently deleted (physical file + DB)
- ℹ️ Shared file removal only affects your view

**Example Usage:**

```bash
# Delete your uploaded file (must be in trash first)
curl -X DELETE http://localhost:8000/api/v1/files/ABC123/permanent-delete/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Remove shared file from your view
curl -X DELETE http://localhost:8000/api/v1/files/XYZ789/permanent-delete/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Use Cases

### 1. Dashboard Overview
Use the "All Files" endpoint to display a unified file manager:
```bash
GET /api/v1/files/all/
```

### 2. My Files Section
Show only user's uploads:
```bash
GET /api/v1/files/my-uploads/
```

### 3. Shared Files Section
Show only files shared with user:
```bash
GET /api/v1/files/shared-with-me/
```

### 4. Trash/Recycle Bin
Show all deleted files with restoration countdown:
```bash
GET /api/v1/files/deleted/
```

### 5. File Details Page
Get comprehensive details about a specific file:
```bash
GET /api/v1/files/ABC123/
```

---

## File Source Types

| Source | Description | Actions Available |
|--------|-------------|-------------------|
| `upload` | Files you uploaded | Download, Share, Delete (soft), Restore, Permanent Delete |
| `shared` | Files shared with you | Download, Remove (permanent) |

**Delete Workflows:**

For **Your Uploads:**
1. Soft delete → `DELETE /api/v1/uploads/{file_code}/` (moves to trash)
2. View trash → `GET /api/v1/files/deleted/`
3. **Restore** → `POST /api/v1/files/{file_code}/restore/` ✅ OR
4. **Permanent delete** → `DELETE /api/v1/files/{file_code}/permanent-delete/` ⚠️

For **Shared Files:**
- Direct removal → `DELETE /api/v1/files/{file_code}/permanent-delete/`
- No trash/restore (just removes from your view)

---

## Integration with Other Apps

### Uploads App
- Uses Upload model for user's uploaded files
- Respects soft delete functionality
- Shares same file_code system

### Sharing App
- Uses SharedFile model for shared content
- Only shows accepted shares
- Maintains sharing metadata (who shared, when)

---

## Response Filtering

All list endpoints automatically filter by:
- ✅ Authenticated user (uploads by user, shares to user)
- ✅ Non-deleted files (except deleted endpoint)
- ✅ Accepted shares only (for shared files)

---

## Notes

- **Unified IDs**: Each file has an `id` (UUID) that corresponds to either Upload.id or SharedFile.id depending on source
- **File Codes**: All files use the file_code system from uploads for consistent identification
- **Deleted Files**: The deleted endpoint shows files from BOTH sources with retention period info
- **Ordering**: Files are ordered by most recent first (uploaded_at for uploads, shared_at for shared)

---

## Testing with cURL

### Get all files
```bash
curl -X GET http://localhost:8000/api/v1/files/all/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get my uploads only
```bash
curl -X GET http://localhost:8000/api/v1/files/my-uploads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get files shared with me
```bash
curl -X GET http://localhost:8000/api/v1/files/shared-with-me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get deleted files (trash)
```bash
curl -X GET http://localhost:8000/api/v1/files/deleted/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get single file details
```bash
curl -X GET http://localhost:8000/api/v1/files/ABC123/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Restore file from trash
```bash
curl -X POST http://localhost:8000/api/v1/files/ABC123/restore/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Permanently delete file
```bash
curl -X DELETE http://localhost:8000/api/v1/files/ABC123/permanent-delete/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "message": "Error description"
}
```

Common error codes:
- `401` - Not authenticated
- `404` - File not found
- `500` - Server error

---

## Best Practices

1. **Use Appropriate Endpoints**: 
   - Use `/all/` for dashboard views
   - Use `/my-uploads/` and `/shared-with-me/` for categorized views
   - Use `/deleted/` for trash management

2. **File Operations**:
   - Use file_code for lookups (not UUID)
   - Check `source` field to determine available actions
   - Respect `days_until_permanent_deletion` for deletion warnings

3. **Performance**:
   - All endpoints use `select_related()` for optimized queries
   - Results are ordered for consistent display

4. **User Experience**:
   - Display `days_until_permanent_deletion` prominently in trash
   - Show file source badges (uploaded/shared)
   - Include owner/sharer information for context
