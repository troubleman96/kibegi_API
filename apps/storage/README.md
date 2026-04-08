# Storage Management App

## Overview

The Storage app is a comprehensive storage management system that tracks and manages user storage usage across the Kibegi platform. Each user receives **50MB of free storage** upon registration, and the app automatically tracks their usage, provides detailed information, and enforces storage limits.

## Features

- ✅ **Automatic Storage Tracking**: Automatically calculates storage usage from uploaded files
- ✅ **Default 50MB Quota**: Every new user gets 50MB of storage on registration
- ✅ **Real-time Usage Information**: Get current storage usage, free space, and percentage used
- ✅ **Storage Limit Enforcement**: Prevents users from uploading files that exceed their quota
- ✅ **Usage History**: Track storage usage over time for analytics
- ✅ **Automatic Updates**: Storage is automatically updated when files are uploaded or deleted
- ✅ **Comprehensive API**: RESTful API endpoints for all storage operations

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Models](#models)
3. [Services](#services)
4. [API Endpoints](#api-endpoints)
5. [Signals](#signals)
6. [Usage Examples](#usage-examples)
7. [Storage Calculation](#storage-calculation)
8. [Admin Interface](#admin-interface)

---

## Installation & Setup

### 1. Add to INSTALLED_APPS

The storage app is already added to `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'storage',
]
```

### 2. Run Migrations

Create and apply database migrations:

```bash
python manage.py makemigrations storage
python manage.py migrate storage
```

### 3. Verify Signals

The app automatically registers signals in `apps.py`. Make sure signals are imported when the app starts.

---

## Models

### UserStorage

The main model that tracks storage for each user.

**Fields:**
- `user`: One-to-one relationship with User model
- `total_quota_mb`: Total storage quota in megabytes (default: 50MB)
- `used_storage_bytes`: Current storage used in bytes (calculated)
- `created_at`: When the storage record was created
- `updated_at`: When the storage record was last updated
- `last_calculated`: Timestamp of last storage calculation

**Computed Properties:**
- `used_storage_mb`: Storage used in megabytes (read-only)
- `free_storage_mb`: Free storage available in megabytes (read-only)
- `free_storage_bytes`: Free storage available in bytes (read-only)
- `usage_percentage`: Storage usage as percentage 0-100 (read-only)
- `is_full`: Boolean indicating if storage is full (read-only)
- `is_near_limit(threshold=90)`: Boolean indicating if near limit (read-only)

**Example:**
```python
from apps.storage.models import UserStorage

storage = UserStorage.objects.get(user=request.user)
print(f"Used: {storage.used_storage_mb}MB")
print(f"Free: {storage.free_storage_mb}MB")
print(f"Usage: {storage.usage_percentage}%")
```

### StorageUsageHistory

Model for tracking historical storage usage snapshots.

**Fields:**
- `user_storage`: Foreign key to UserStorage
- `used_storage_bytes`: Storage used at this point in time
- `recorded_at`: When this snapshot was recorded

**Use Case:**
Track storage growth over time for analytics and reporting.

---

## Services

### StorageService

The main service class for all storage operations.

#### Methods

##### `get_or_create_user_storage(user)`
Get or create a storage record for a user.

```python
from apps.storage.services import StorageService

storage = StorageService.get_or_create_user_storage(user)
```

##### `calculate_user_storage(user)`
Calculate total storage used by a user from all uploaded files.

```python
used_bytes = StorageService.calculate_user_storage(user)
```

**How it works:**
1. Sums file sizes from `uploads.Upload` model
2. Sums file sizes from `files.File` model (if exists)
3. Returns total bytes used

##### `update_user_storage(user, recalculate=True)`
Update a user's storage record with current usage.

```python
storage = StorageService.update_user_storage(user, recalculate=True)
```

##### `get_storage_info(user)`
Get comprehensive storage information dictionary.

```python
info = StorageService.get_storage_info(user)
# Returns:
# {
#     'total_quota_mb': 50.0,
#     'used_storage_mb': 12.5,
#     'free_storage_mb': 37.5,
#     'used_storage_bytes': 13107200,
#     'free_storage_bytes': 39321600,
#     'usage_percentage': 25.0,
#     'is_full': False,
#     'is_near_limit': False,
#     'last_calculated': '2025-11-25T10:00:00Z'
# }
```

##### `can_upload_file(user, file_size_bytes)`
Check if a user can upload a file of the given size.

```python
can_upload, error_message = StorageService.can_upload_file(user, file_size_bytes=5000000)

if not can_upload:
    print(f"Upload failed: {error_message}")
```

**Returns:**
- `(True, None)` if upload is allowed
- `(False, error_message)` if upload would exceed quota

##### `increase_storage_quota(user, additional_mb)`
Increase a user's storage quota (e.g., for premium users).

```python
storage = StorageService.increase_storage_quota(user, additional_mb=50.0)
```

##### `set_storage_quota(user, quota_mb)`
Set a user's storage quota to a specific value.

```python
storage = StorageService.set_storage_quota(user, quota_mb=100.0)
```

---

## API Endpoints

All endpoints require authentication (JWT token).

### Base URL
```
/api/v1/storage/
```

### 1. Get Storage Information

**GET** `/api/v1/storage/`

Get current user's storage information.

**Response:**
```json
{
  "success": true,
  "message": "Storage information retrieved successfully",
  "data": {
    "id": 1,
    "user": 1,
    "user_email": "user@example.com",
    "user_full_name": "John Doe",
    "total_quota_mb": 50.0,
    "used_storage_bytes": 13107200,
    "used_storage_mb": 12.5,
    "free_storage_mb": 37.5,
    "free_storage_bytes": 39321600,
    "usage_percentage": 25.0,
    "is_full": false,
    "is_near_limit": false,
    "created_at": "2025-11-25T08:00:00Z",
    "updated_at": "2025-11-25T10:00:00Z",
    "last_calculated": "2025-11-25T10:00:00Z"
  }
}
```

### 2. Get Detailed Storage Info

**GET** `/api/v1/storage/info/`

Get detailed storage information in a user-friendly format.

**Response:**
```json
{
  "success": true,
  "message": "Storage information retrieved successfully",
  "data": {
    "total_quota_mb": 50.0,
    "used_storage_mb": 12.5,
    "free_storage_mb": 37.5,
    "used_storage_bytes": 13107200,
    "free_storage_bytes": 39321600,
    "usage_percentage": 25.0,
    "is_full": false,
    "is_near_limit": false,
    "last_calculated": "2025-11-25T10:00:00Z"
  }
}
```

### 3. Recalculate Storage

**POST** `/api/v1/storage/recalculate/`

Manually trigger storage recalculation (useful if storage seems incorrect).

**Response:**
```json
{
  "success": true,
  "message": "Storage recalculated successfully",
  "data": {
    "total_quota_mb": 50.0,
    "used_storage_mb": 12.5,
    "free_storage_mb": 37.5,
    "usage_percentage": 25.0,
    "is_full": false,
    "is_near_limit": false
  }
}
```

### 4. Get Usage History

**GET** `/api/v1/storage/history/`

Get historical storage usage snapshots.

**Query Parameters:**
- `limit`: Number of records to return (default: 30)

**Response:**
```json
{
  "success": true,
  "message": "Storage history retrieved successfully",
  "data": [
    {
      "id": 1,
      "user_storage": 1,
      "used_storage_bytes": 13107200,
      "used_storage_mb": 12.5,
      "recorded_at": "2025-11-25T10:00:00Z"
    },
    {
      "id": 2,
      "user_storage": 1,
      "used_storage_bytes": 10485760,
      "used_storage_mb": 10.0,
      "recorded_at": "2025-11-24T10:00:00Z"
    }
  ]
}
```

---

## Signals

The app uses Django signals to automatically manage storage:

### 1. User Creation Signal

**Signal:** `post_save` on `User` model

**Action:** Automatically creates a `UserStorage` record with 50MB quota when a new user registers.

**Location:** `storage/signals.py`

### 2. File Upload Signal

**Signal:** `post_save` on `uploads.Upload` model

**Action:** Automatically updates user storage when a file is uploaded.

**Location:** `storage/signals.py`

### 3. File Deletion Signal

**Signal:** `post_delete` on `uploads.Upload` model

**Action:** Automatically updates user storage when a file is deleted.

**Location:** `storage/signals.py`

### 4. Files App Signals

Similar signals for `files.File` model (if files app exists).

---

## Usage Examples

### Example 1: Check Storage Before Upload

```python
from apps.storage.services import StorageService

def upload_file_view(request):
    file_size = request.FILES['file'].size
    
    # Check if user can upload
    can_upload, error_message = StorageService.can_upload_file(
        request.user, 
        file_size
    )
    
    if not can_upload:
        return Response(
            {"error": error_message},
            status=400
        )
    
    # Proceed with upload
    # ... upload logic ...
```

### Example 2: Get Storage Info in View

```python
from apps.storage.services import StorageService
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_storage_view(request):
    info = StorageService.get_storage_info(request.user)
    return Response(info)
```

### Example 3: Display Storage in Frontend

```javascript
// Fetch storage information
fetch('/api/v1/storage/info/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(response => response.json())
.then(data => {
  const storage = data.data;
  
  console.log(`Total: ${storage.total_quota_mb}MB`);
  console.log(`Used: ${storage.used_storage_mb}MB`);
  console.log(`Free: ${storage.free_storage_mb}MB`);
  console.log(`Usage: ${storage.usage_percentage}%`);
  
  // Display progress bar
  const progressBar = document.getElementById('storage-progress');
  progressBar.style.width = `${storage.usage_percentage}%`;
  progressBar.textContent = `${storage.usage_percentage}%`;
  
  // Show warning if near limit
  if (storage.is_near_limit) {
    alert('Warning: You are running low on storage space!');
  }
});
```

### Example 4: React Component

```jsx
import React, { useState, useEffect } from 'react';

function StorageInfo() {
  const [storage, setStorage] = useState(null);
  
  useEffect(() => {
    fetch('/api/v1/storage/info/', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    .then(res => res.json())
    .then(data => setStorage(data.data));
  }, []);
  
  if (!storage) return <div>Loading...</div>;
  
  return (
    <div className="storage-info">
      <h3>Storage Usage</h3>
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${storage.usage_percentage}%` }}
        />
      </div>
      <p>
        {storage.used_storage_mb}MB / {storage.total_quota_mb}MB used
      </p>
      <p>
        {storage.free_storage_mb}MB free
      </p>
      {storage.is_near_limit && (
        <p className="warning">
          ⚠️ You are running low on storage space!
        </p>
      )}
    </div>
  );
}
```

---

## Storage Calculation

### How Storage is Calculated

1. **Source Models:**
   - `uploads.Upload` model: Sums all `file_size` fields
   - `files.File` model: Sums all `file_size` fields (if exists)

2. **Calculation Process:**
   ```python
   # Step 1: Get all uploads for user
   uploads_total = Upload.objects.filter(uploader=user).aggregate(
       total=Sum('file_size')
   )['total'] or 0
   
   # Step 2: Get all files for user (if files app exists)
   files_total = File.objects.filter(uploader=user).aggregate(
       total=Sum('file_size')
   )['total'] or 0
   
   # Step 3: Sum total
   total_bytes = uploads_total + files_total
   ```

3. **Automatic Updates:**
   - Storage is recalculated automatically when files are uploaded/deleted via signals
   - Can be manually triggered via API endpoint or service method

### Storage Units

- **Bytes**: Raw file size in bytes
- **Megabytes (MB)**: `bytes / (1024 * 1024)`
- **Quota**: Stored in MB, converted to bytes for calculations

---

## Admin Interface

The storage app provides a comprehensive admin interface:

### UserStorage Admin

**Features:**
- List view with search and filters
- Detailed view with all storage information
- Read-only computed fields
- Filter by: `is_full`, `total_quota_mb`, `last_calculated`
- Search by: `user__email`, `user__full_name`

**Access:** `/admin/storage/userstorage/`

### StorageUsageHistory Admin

**Features:**
- Historical storage snapshots
- Date hierarchy for easy navigation
- Filter by date

**Access:** `/admin/storage/storageusagehistory/`

---

## Configuration

### Default Storage Quota

The default storage quota is set in `storage/services.py`:

```python
class StorageService:
    DEFAULT_QUOTA_MB = 50.0  # Change this to modify default quota
```

### Custom Quota Per User

You can set custom quotas for specific users:

```python
from apps.storage.services import StorageService

# Set custom quota
StorageService.set_storage_quota(user, quota_mb=100.0)

# Or increase existing quota
StorageService.increase_storage_quota(user, additional_mb=50.0)
```

---

## Error Handling

### Common Errors

1. **Storage Full:**
   - Error: `"Insufficient storage space"`
   - Solution: Delete files or increase quota

2. **Storage Calculation Failed:**
   - Error: `"Failed to calculate storage"`
   - Solution: Check file models exist and have `file_size` field

3. **Storage Record Not Found:**
   - Error: `"Storage record not found"`
   - Solution: Storage record is auto-created, but can be manually created:
     ```python
     StorageService.get_or_create_user_storage(user)
     ```

---

## Testing

### Manual Testing

1. **Create a user** - Storage record should be auto-created
2. **Upload files** - Storage should update automatically
3. **Delete files** - Storage should update automatically
4. **Check API endpoints** - All endpoints should return correct data

### API Testing with curl

```bash
# Get storage info
curl -X GET http://localhost:8000/api/v1/storage/info/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Recalculate storage
curl -X POST http://localhost:8000/api/v1/storage/recalculate/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Troubleshooting

### Storage Not Updating

1. **Check signals are registered:**
   - Verify `storage.signals` is imported in `apps.py`
   - Check app is in `INSTALLED_APPS`

2. **Check file models:**
   - Ensure `uploads.Upload` has `file_size` field
   - Ensure `files.File` has `file_size` field (if exists)

3. **Manual recalculation:**
   ```python
   StorageService.update_user_storage(user, recalculate=True)
   ```

### Incorrect Storage Calculation

1. **Recalculate manually:**
   ```python
   StorageService.update_user_storage(user, recalculate=True)
   ```

2. **Check file sizes:**
   - Verify `file_size` field is populated correctly
   - Check for null or zero values

---

## Future Enhancements

Potential improvements:
- [ ] Storage usage alerts/notifications
- [ ] Storage usage charts/graphs
- [ ] Automatic cleanup of old files
- [ ] Storage quota tiers (free, premium, etc.)
- [ ] Storage usage reports
- [ ] Bulk storage operations

---

## Support

For issues or questions:
1. Check this README
2. Review code comments
3. Check Django admin for storage records
4. Review API documentation at `/api/docs/`

---

## License

Part of the Kibegi Digital School platform.


