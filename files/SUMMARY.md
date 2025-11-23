# Files App - Summary

## Overview
The **Files App** is a unified aggregation layer that brings together file content from both the **Uploads** and **Sharing** apps into a single, convenient API.

## Purpose
Instead of having to query multiple endpoints to see all your files, the Files app provides:
- A single endpoint to see ALL your files (uploads + shared)
- Separate views for uploads vs shared files
- A unified deleted files view showing trash from both sources
- Quick file lookup by file_code across both systems

## Key Features

### 1. **Unified File View** (`/api/v1/files/all/`)
- Combines your uploads with files shared with you
- Shows complete file information including source
- Indicates whether file is yours or shared with you

### 2. **Filtered Views**
- **My Uploads** (`/my-uploads/`): Only files you uploaded
- **Shared With Me** (`/shared-with-me/`): Only files others shared with you

### 3. **Unified Trash** (`/deleted/`)
- Shows deleted files from BOTH uploads and sharing
- Displays days until permanent deletion (21-day retention)
- Helps track all recoverable files in one place

### 4. **Quick Lookup** (`/{file_code}/`)
- Find any file by its file_code
- Searches both uploads and shared files automatically
- Returns complete file details

## Architecture

### No Database Models
The Files app doesn't create any new models or database tables. It's purely an aggregation layer that:
- Queries existing Upload and SharedFile models
- Combines and formats the data
- Presents it in a unified format

### Data Flow
```
┌─────────────┐     ┌──────────────┐
│   Uploads   │────▶│              │
│   (Model)   │     │  Files App   │────▶ Unified Response
│             │     │  (Aggregator)│
└─────────────┘     │              │
                    │              │
┌─────────────┐     │              │
│   Sharing   │────▶│              │
│   (Model)   │     │              │
└─────────────┘     └──────────────┘
```

## Components

### Serializers (`serializers.py`)
1. **FileOwnerSerializer**: User information
2. **UnifiedFileSerializer**: Combined file data with source indication
3. **DeletedFileSerializer**: Deleted files with retention info

### Views (`views.py`)
1. **AllFilesAPIView**: All files (uploads + accepted shares)
2. **MyUploadsAPIView**: User's uploads only
3. **SharedWithMeAPIView**: Accepted shared files only
4. **DeletedFilesAPIView**: All deleted files from both sources
5. **SingleFileDetailAPIView**: Single file lookup by file_code

### URLs (`urls.py`)
- `/all/` - All files
- `/my-uploads/` - My uploads
- `/shared-with-me/` - Shared files
- `/deleted/` - Deleted files (trash)
- `/{file_code}/` - Single file detail

## Benefits

### For Frontend Developers
- Single API call for dashboard file lists
- Consistent response format across all endpoints
- Easy filtering by source (upload vs shared)
- Unified trash management

### For Users
- See all accessible files in one view
- Track deleted files from all sources
- Quick file search across everything
- Clear indication of file ownership

### For System Architecture
- Separation of concerns (uploads/sharing logic separate)
- No duplication of file data
- Consistent with existing soft-delete patterns
- Easy to extend with new file sources

## Integration

### With Uploads App
- Uses Upload model for uploaded files
- Respects soft delete functionality (is_deleted, deleted_at)
- Uses file_code for identification
- Shows uploader as owner

### With Sharing App
- Uses SharedFile model for shared content
- Only shows accepted shares (accepted=True)
- Respects soft delete on shared files
- Shows original uploader and who shared it

## Use Cases

### 1. File Manager Dashboard
Display all accessible files with tabs:
```javascript
// All Files Tab
GET /api/v1/files/all/

// My Uploads Tab
GET /api/v1/files/my-uploads/

// Shared Tab
GET /api/v1/files/shared-with-me/
```

### 2. Trash/Recycle Bin
Show all deleted files with recovery countdown:
```javascript
GET /api/v1/files/deleted/
// Returns files from both uploads and sharing with days_until_permanent_deletion
```

### 3. Quick File Search
Find file by code across all sources:
```javascript
GET /api/v1/files/ABC123/
// Searches uploads first, then shared files
```

### 4. File Source Badge
Display appropriate badges based on source:
```javascript
if (file.source === 'upload') {
  badge = 'Your File';
} else if (file.source === 'shared') {
  badge = `Shared by ${file.shared_by.username}`;
}
```

## Response Format

All endpoints return consistent structure:
```json
{
  "success": true,
  "message": "Retrieved X files",
  "data": [
    {
      "id": "uuid",
      "file_code": "ABC123",
      "file_name": "document.pdf",
      "file_size": 2048576,
      "file_type": "application/pdf",
      "file_url": "http://...",
      "source": "upload" | "shared",
      "owner": { user_object },
      "uploaded_at": "timestamp",
      "is_deleted": false,
      "deleted_at": null,
      "shared_by": { user_object } | null,
      "shared_at": "timestamp" | null,
      "accepted": true | null
    }
  ]
}
```

## Testing

After server restart, test the endpoints:

```bash
# All files
curl -X GET http://localhost:8000/api/v1/files/all/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# My uploads
curl -X GET http://localhost:8000/api/v1/files/my-uploads/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Shared with me
curl -X GET http://localhost:8000/api/v1/files/shared-with-me/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Deleted files
curl -X GET http://localhost:8000/api/v1/files/deleted/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Single file
curl -X GET http://localhost:8000/api/v1/files/ABC123/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Future Enhancements

Potential additions:
- [ ] Filtering by file_type (documents, images, videos)
- [ ] Sorting options (size, date, name)
- [ ] Pagination for large file lists
- [ ] Search within file names
- [ ] Bulk operations (multi-delete, multi-restore)
- [ ] File statistics (total size, counts by type)

## Notes

- **No migrations needed**: App doesn't define models
- **Read-only operations**: Uses existing models for queries
- **Optimized queries**: Uses select_related() for performance
- **Consistent with system**: Follows existing patterns and conventions
- **Fully documented**: Complete README with examples
- **OpenAPI/Swagger**: All endpoints documented for API docs

## File Structure

```
files/
├── __init__.py
├── apps.py
├── serializers.py      # Data formatting
├── views.py            # API endpoints (5 views)
├── urls.py             # URL routing
├── README.md           # Full API documentation
└── SUMMARY.md          # This file
```

## Installation Complete

✅ App created and configured
✅ Registered in settings.py
✅ URLs added to main urls.py
✅ No errors on `python manage.py check`
✅ No migrations needed
✅ Ready to use after server restart
