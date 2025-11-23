# File Sharing System

Complete file sharing implementation for the Kibegi platform, enabling secure file sharing between class members with request/accept workflow.

## Table of Contents
- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Permission System](#permission-system)
- [Request/Accept Flow](#requestaccept-flow)
- [Testing Guide](#testing-guide)
- [Common Errors](#common-errors)

---

## Overview

The file sharing system allows users to share uploaded files with other members of their class. It implements a request/accept pattern where:

1. **File Owner** shares a file with another user
2. **Recipient** receives a pending share request
3. **Recipient** can accept or reject the share
4. **Accepted shares** grant access to the file

### Key Features

- **Permission-Based**: Only file uploaders can share their files
- **Class-Scoped**: Users can only share with members of the same class
- **Status Tracking**: Three states - pending, accepted, rejected
- **Duplicate Prevention**: Cannot share same file with same user twice
- **Bulk Sharing**: Share with multiple users in one request (max 50)
- **Asynchronous Processing**: Background tasks prevent blocking when receivers delay
- **Non-Blocking Notifications**: Notifications sent asynchronously to prevent API delays
- **Optimized Queries**: Uses select_related/prefetch_related for performance

---

## Models

### SharedFile

Represents a file share between two users.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `upload` | ForeignKey | The uploaded file being shared |
| `shared_by` | ForeignKey | User who shared the file |
| `shared_with` | ForeignKey | User receiving the share |
| `status` | CharField | Current status: `pending`, `accepted`, `rejected` |
| `message` | TextField | Optional message from sharer (max 500 chars) |
| `shared_at` | DateTimeField | When share was created |
| `accepted_at` | DateTimeField | When share was accepted (null if not accepted) |
| `rejected_at` | DateTimeField | When share was rejected (null if not rejected) |

#### Constraints

- **unique_together**: `['upload', 'shared_with']` - Prevents duplicate shares
- **Index on**: `['status', 'shared_at']` - For efficient filtering
- **Index on**: `['shared_with', 'status']` - For user-specific queries

#### Model Methods

```python
def accept():
    """Accept a pending share request"""
    
def reject():
    """Reject a pending share request"""
    
def is_pending() -> bool:
    """Check if share is pending"""
    
def is_accepted() -> bool:
    """Check if share is accepted"""
    
def is_rejected() -> bool:
    """Check if share is rejected"""

@property
def can_access_file() -> bool:
    """Check if recipient can access the file (accepted + file not deleted)"""
```

---

## API Endpoints

All endpoints require authentication. Base path: `/api/v1/sharing/`

### 1. Share a File

**POST** `/api/v1/sharing/`

Share one of your uploaded files with another user in your class.

#### Request Body

```json
{
    "file_code": "ABC12345",
    "shared_with_id": 42,
    "message": "Check out this study material!"
}
```

#### Success Response (201)

```json
{
    "success": true,
    "message": "File shared successfully. Recipient will be notified.",
    "data": {
        "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "upload": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "file_code": "ABC12345",
            "file_name": "lecture_notes.pdf",
            "file_type": "document",
            "file_size": 2048576
        },
        "shared_by": "123e4567-e89b-12d3-a456-426614174000",
        "shared_by_name": "John Doe",
        "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "shared_with_name": "Jane Smith",
        "status": "pending",
        "message": "Check out this study material!",
        "shared_at": "2024-01-15T10:30:00Z",
        "accepted_at": null,
        "rejected_at": null,
        "can_access": false
    }
}
```

#### Error Responses

- `400`: File not found, not your file, user not found, duplicate share
- `401`: Not authenticated
- `403`: Don't have permission to share

---

### 2. Bulk Share

**POST** `/api/v1/sharing/bulk/`

Share a file with multiple users at once (max 50 users).

#### Request Body

```json
{
    "file_code": "ABC12345",
    "user_ids": [42, 43, 44],
    "message": "Study materials for the exam"
}
```

#### Success Response (202 Accepted)

**Note**: Bulk sharing is processed asynchronously to prevent blocking when sharing with many users or when receivers are slow to respond.

```json
{
    "success": true,
    "message": "Sharing with 3 users in progress. Recipients will be notified.",
    "data": {
        "status": "processing",
        "user_count": 3,
        "file_code": "ABC12345"
    }
}
```

---

### 3. List Pending Requests

**GET** `/api/v1/sharing/requests/`

Get all pending share requests sent to you (awaiting your action).

#### Query Parameters

None (automatically filters to pending status)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Pending requests retrieved successfully",
    "data": {
        "count": 2,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
                "file_name": "lecture_notes.pdf",
                "file_type": "document",
                "file_code": "ABC12345",
                "shared_by": "123e4567-e89b-12d3-a456-426614174000",
                "shared_by_name": "John Doe",
                "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
                "shared_with_name": "Jane Smith",
                "status": "pending",
                "message": "Important study material",
                "shared_at": "2024-01-15T10:30:00Z"
            },
            {
                "id": "456789ab-cdef-0123-4567-89abcdef0123",
                "file_name": "assignment.docx",
                "file_type": "document",
                "file_code": "XYZ98765",
                "shared_by": "234567ef-abcd-1234-5678-9abcdef01234",
                "shared_by_name": "Mike Johnson",
                "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
                "shared_with_name": "Jane Smith",
                "status": "pending",
                "message": "",
                "shared_at": "2024-01-15T11:00:00Z"
            }
        ]
    }
}
```

---

### 4. List Files Shared With Me

**GET** `/api/v1/sharing/shared-with-me/`

Get all files that have been shared with you.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `accepted`, or `rejected` (optional) |

#### Example Requests

```bash
# Get all shares (any status)
GET /api/v1/sharing/shared-with-me/

# Get only accepted shares (files you can access)
GET /api/v1/sharing/shared-with-me/?status=accepted

# Get rejected shares
GET /api/v1/sharing/shared-with-me/?status=rejected
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Shared files retrieved successfully",
    "data": {
        "count": 5,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
                "file_name": "lecture_notes.pdf",
                "file_type": "document",
                "file_code": "ABC12345",
                "shared_by": "123e4567-e89b-12d3-a456-426614174000",
                "shared_by_name": "John Doe",
                "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
                "shared_with_name": "Jane Smith",
                "status": "accepted",
                "message": "Study material",
                "shared_at": "2024-01-15T10:30:00Z"
            }
        ]
    }
}
```

---

### 5. List My Shares

**GET** `/api/v1/sharing/my-shares/`

Get all files you have shared with other users.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `accepted`, or `rejected` (optional) |

#### Example Requests

```bash
# Get all your shares
GET /api/v1/sharing/my-shares/

# Get shares that are still pending
GET /api/v1/sharing/my-shares/?status=pending

# Get accepted shares
GET /api/v1/sharing/my-shares/?status=accepted
```

---

### 6. Accept a Share

**POST** `/api/v1/sharing/{share_id}/accept/`

Accept a pending share request to gain access to the file.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `share_id` | UUID | ID of the share to accept |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Share accepted successfully. You can now access the file.",
    "data": {
        "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "upload": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "file_code": "ABC12345",
            "file_name": "lecture_notes.pdf",
            "file_type": "document",
            "file_size": 2048576
        },
        "shared_by": "123e4567-e89b-12d3-a456-426614174000",
        "shared_by_name": "John Doe",
        "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "shared_with_name": "Jane Smith",
        "status": "accepted",
        "message": "Study material",
        "shared_at": "2024-01-15T10:30:00Z",
        "accepted_at": "2024-01-15T11:00:00Z",
        "rejected_at": null,
        "can_access": true
    }
}
```

#### Error Responses

- `400`: Share already accepted
- `403`: Not the recipient of this share
- `404`: Share not found

---

### 7. Reject a Share

**POST** `/api/v1/sharing/{share_id}/reject/`

Reject a pending share request.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `share_id` | UUID | ID of the share to reject |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Share rejected",
    "data": {
        "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "upload": {...},
        "status": "rejected",
        "rejected_at": "2024-01-15T11:00:00Z"
    }
}
```

---

### 8. Get Share Details

**GET** `/api/v1/sharing/{share_id}/`

Get detailed information about a specific share.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `share_id` | UUID | ID of the share |

#### Success Response (200)

```json
{
    "success": true,
    "message": "Share details retrieved successfully",
    "data": {
        "id": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "upload": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "file_code": "ABC12345",
            "file_name": "lecture_notes.pdf",
            "file_type": "document",
            "file_size": 2048576,
            "uploaded_by": "123e4567-e89b-12d3-a456-426614174000",
            "uploaded_at": "2024-01-15T09:00:00Z"
        },
        "shared_by": "123e4567-e89b-12d3-a456-426614174000",
        "shared_by_name": "John Doe",
        "shared_with": "987fcdeb-51a2-43b7-a123-456789abcdef",
        "shared_with_name": "Jane Smith",
        "status": "accepted",
        "message": "Study material for exam",
        "shared_at": "2024-01-15T10:30:00Z",
        "accepted_at": "2024-01-15T11:00:00Z",
        "rejected_at": null,
        "can_access": true
    }
}
```

---

### 9. Download Shared File

**GET** `/api/v1/sharing/{share_id}/download/`

Download a file that has been shared with you and accepted.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `share_id` | UUID | ID of the share |

#### Requirements

- ✅ You must be the recipient (`shared_with`)
- ✅ Share must be accepted (`status = 'accepted'`)
- ✅ File must not be deleted by owner

#### Success Response (200)

Returns the file as binary data with headers:
```
Content-Type: application/pdf (or appropriate MIME type)
Content-Disposition: attachment; filename="document.pdf"
Content-Length: 2456789
Cache-Control: private, max-age=3600
X-Content-Type-Options: nosniff
```

The browser will automatically download the file with the correct filename.

#### Example Usage

**Browser (Direct Link):**
```html
<a href="http://localhost:8000/api/v1/sharing/{share_id}/download/" 
   download>
  Download Shared File
</a>
```

**JavaScript (Fetch API):**
```javascript
async function downloadSharedFile(shareId, fileName) {
  const response = await fetch(
    `http://localhost:8000/api/v1/sharing/${shareId}/download/`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  if (response.ok) {
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }
}

// Usage
downloadSharedFile('987fcdeb-51a2-43b7-a123-456789abcdef', 'document.pdf');
```

**cURL:**
```bash
# Download with authentication
curl -X GET http://localhost:8000/api/v1/sharing/{share_id}/download/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o downloaded-file.pdf

# Or let cURL detect filename from headers
curl -OJ http://localhost:8000/api/v1/sharing/{share_id}/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Mobile App (React Native):**
```javascript
import RNFS from 'react-native-fs';

async function downloadSharedFile(shareId, fileName) {
  const downloadUrl = `http://localhost:8000/api/v1/sharing/${shareId}/download/`;
  const downloadDest = `${RNFS.DocumentDirectoryPath}/${fileName}`;
  
  const download = RNFS.downloadFile({
    fromUrl: downloadUrl,
    toFile: downloadDest,
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const result = await download.promise;
  if (result.statusCode === 200) {
    console.log('File downloaded to:', downloadDest);
  }
}
```

#### Error Responses

| Status | Error | Cause |
|--------|-------|-------|
| `403` | Not authorized | You are not the recipient of the share |
| `403` | Share not accepted | Share status is pending or rejected |
| `404` | Share not found | Invalid share_id or share doesn't exist |
| `404` | File deleted | File owner deleted the original file |
| `404` | File not on server | File missing from storage |

#### Use Cases

- **Study Materials**: Download lecture notes shared by classmates
- **Cross-Device**: Start on PC, download on mobile
- **Offline Access**: Download files for offline viewing
- **Project Files**: Access shared project documents

---

## Asynchronous Processing

The sharing system uses background threading to prevent API blocking when receivers delay or are offline.

### Why Async?

When sharing files or accepting/rejecting shares, the system needs to:
1. Create database records
2. Send notifications to users
3. Potentially wait for external services

If any of these operations are slow (user offline, network issues, high load), synchronous processing would block the API and create poor user experience.

### What Runs in Background?

#### Bulk Sharing
- **Fully Async**: Returns `202 Accepted` immediately
- Processes all shares in background thread
- Users notified asynchronously as shares complete
- Prevents timeout when sharing with many users

```python
# User makes request
POST /api/v1/sharing/bulk/

# API returns immediately with 202 Accepted
{
    "status": "processing",
    "user_count": 50
}

# Background thread processes all 50 shares
# Notifications sent as each share completes
```

#### Accept/Reject Actions
- **Sync**: Share status updated immediately
- **Async**: Notifications sent in background
- Prevents blocking if sharer is offline

```python
# User accepts share
POST /api/v1/sharing/{id}/accept/

# Status changes immediately (sync)
# Notification to sharer sent in background (async)
```

### Threading Model

The system uses Python's `threading` module with daemon threads:

```python
def create_share_async(upload, shared_by, shared_with, message):
    """Background thread handles notification delays"""
    
    def _create_share():
        with transaction.atomic():
            share = SharingService.create_share(...)
            # Send notification (may be slow)
            NotificationService.notify(...)
    
    # Start thread, return immediately
    thread = threading.Thread(target=_create_share, daemon=True)
    thread.start()
    return thread
```

### Benefits

✅ **Fast Response**: API returns immediately, no waiting  
✅ **Better UX**: Users not blocked by slow operations  
✅ **Scalability**: Handle high load without timeouts  
✅ **Reliability**: Offline users don't block online users  
✅ **Graceful Degradation**: Failed notifications don't crash API

### Error Handling

Background threads log errors but don't crash:

```python
try:
    # Process share
    share = create_share(...)
except Exception as e:
    logger.error(f"Failed to create share: {e}")
    # Error logged, thread exits gracefully
```

### Future Enhancements

For production, consider:
- **Celery**: Distributed task queue with retry logic
- **Redis**: Message broker for task distribution
- **Database Tasks**: Persistent task queue with status tracking
- **Webhooks**: Real-time notification delivery

---

## Permission System

### Who Can Share?

✅ **Allowed**: File uploader (owner)  
❌ **Denied**: Other users, even if file was shared with them

### Who Can Receive?

✅ **Allowed**: Users in the same class as the file  
❌ **Denied**: Users not in that class, deleted users

### Who Can Accept/Reject?

✅ **Allowed**: The recipient of the share  
❌ **Denied**: The sharer, other users

### Permission Checks

The system validates:

1. **File Ownership**: Only the uploader can share
2. **Class Membership**: Both users must be in the same class
3. **User Status**: Neither user can be deleted
4. **Duplicate Prevention**: Cannot share same file with same user twice
5. **Recipient Validation**: Only recipient can accept/reject

---

## Request/Accept Flow

### Complete Workflow

```
┌─────────────┐
│   Upload    │
│    File     │
└──────┬──────┘
       │
       v
┌─────────────┐         ┌──────────────┐
│   Share     │────────>│   Pending    │
│    File     │         │   Request    │
└─────────────┘         └──────┬───────┘
                               │
                    ┌──────────┴──────────┐
                    v                     v
             ┌──────────┐         ┌──────────┐
             │  Accept  │         │  Reject  │
             └────┬─────┘         └────┬─────┘
                  │                    │
                  v                    v
          ┌──────────────┐     ┌──────────────┐
          │   Accepted   │     │   Rejected   │
          │ (Can Access) │     │ (No Access)  │
          └──────────────┘     └──────────────┘
```

### Status Transitions

| From | To | Action | Who |
|------|-----|--------|-----|
| - | `pending` | Share file | File owner |
| `pending` | `accepted` | Accept share | Recipient |
| `pending` | `rejected` | Reject share | Recipient |
| `accepted` | - | Cannot change | - |
| `rejected` | - | Cannot change | - |

### State Properties

| Status | Can Access File | Can Re-share | Timestamps |
|--------|-----------------|--------------|------------|
| `pending` | ❌ No | ❌ No | `shared_at` |
| `accepted` | ✅ Yes | ❌ No | `shared_at`, `accepted_at` |
| `rejected` | ❌ No | ❌ No | `shared_at`, `rejected_at` |

---

## Testing Guide

### Using Swagger UI

1. **Navigate to Swagger**
   ```
   http://localhost:8000/api/schema/swagger-ui/
   ```

2. **Authenticate**
   - Click "Authorize" button
   - Enter: `Bearer <your_access_token>`
   - Click "Authorize"

3. **Test Flow**

   **Step 1: Upload a file first**
   ```
   POST /api/v1/uploads/
   ```

   **Step 2: Share the file**
   ```
   POST /api/v1/sharing/
   Body: {
       "file_code": "ABC12345",
       "shared_with_id": "<recipient_user_id>",
       "message": "Test share"
   }
   ```

   **Step 3: Recipient views pending requests**
   ```
   GET /api/v1/sharing/requests/
   (Login as recipient first)
   ```

   **Step 4: Accept the share**
   ```
   POST /api/v1/sharing/{share_id}/accept/
   ```

   **Step 5: View accepted files**
   ```
   GET /api/v1/sharing/shared-with-me/?status=accepted
   ```

   **Step 6: Download shared file**
   ```
   GET /api/v1/sharing/{share_id}/download/
   ```
   File downloads automatically with correct filename

### Using cURL

#### 1. Login and Get Tokens

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "password123"
  }'

# Extract access_token from response
export TOKEN="<your_access_token>"
```

#### 2. Share a File

```bash
curl -X POST http://localhost:8000/api/v1/sharing/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_code": "ABC12345",
    "shared_with_id": 42,
    "message": "Check this out!"
  }'
```

#### 3. Bulk Share

```bash
curl -X POST http://localhost:8000/api/v1/sharing/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_code": "ABC12345",
    "user_ids": [42, 43],
    "message": "Study materials"
  }'
```

#### 4. List Pending Requests

```bash
curl -X GET http://localhost:8000/api/v1/sharing/requests/ \
  -H "Authorization: Bearer $TOKEN"
```

#### 5. List Shared With Me (Accepted Only)

```bash
curl -X GET "http://localhost:8000/api/v1/sharing/shared-with-me/?status=accepted" \
  -H "Authorization: Bearer $TOKEN"
```

#### 6. Accept a Share

```bash
curl -X POST http://localhost:8000/api/v1/sharing/{share_id}/accept/ \
  -H "Authorization: Bearer $TOKEN"
```

#### 7. Reject a Share

```bash
curl -X POST http://localhost:8000/api/v1/sharing/{share_id}/reject/ \
  -H "Authorization: Bearer $TOKEN"
```

#### 8. Get Share Details

```bash
curl -X GET http://localhost:8000/api/v1/sharing/{share_id}/ \
  -H "Authorization: Bearer $TOKEN"
```

#### 9. Download Shared File

```bash
# Download with auto-detected filename
curl -OJ http://localhost:8000/api/v1/sharing/{share_id}/download/ \
  -H "Authorization: Bearer $TOKEN"

# Or specify output filename
curl -o myfile.pdf http://localhost:8000/api/v1/sharing/{share_id}/download/ \
  -H "Authorization: Bearer $TOKEN"
```

### Testing Scenarios

#### Scenario 1: Successful Share with Download

1. User A uploads file → Gets file_code
2. User A shares with User B → Returns pending share
3. User B lists requests → Sees pending share
4. User B accepts → Status becomes accepted
5. User B downloads the file → File downloads with original name

#### Scenario 2: Rejected Share

1. User A shares file with User B
2. User B rejects the share
3. User B cannot access the file
4. Share remains in rejected state

#### Scenario 3: Permission Validation

1. User A uploads file
2. User B (not uploader) tries to share → **Error**: Not your file
3. User A shares with User C (different class) → **Error**: Not in same class
4. User A tries to accept own share → **Error**: Only recipient can accept

#### Scenario 4: Duplicate Prevention

1. User A shares file with User B → Success
2. User A tries to share same file with User B again → **Error**: Already shared

#### Scenario 5: Bulk Share

1. User A shares file with 3 users
2. 2 are in same class → Success
3. 1 is in different class → Error in results
4. Returns: 2 successes, 1 error with reason

---

## Common Errors

### 400 Bad Request

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `File not found or has been deleted` | Invalid file_code or deleted file | Use valid file_code from uploads |
| `This is not your file to share` | Trying to share someone else's file | Only share your own uploads |
| `User not found` | Invalid shared_with_id | Use valid user UUID |
| `Shared user is not in the same class` | Users in different classes | Both must be in same class |
| `You have already shared this file with this user` | Duplicate share | Check existing shares first |
| `Share already accepted` | Accepting accepted share | Check status before accepting |
| `Share already rejected` | Rejecting rejected share | Check status before rejecting |

### 401 Unauthorized

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Authentication credentials were not provided` | Missing token | Include `Authorization: Bearer <token>` |
| `Given token not valid` | Expired/invalid token | Get new token via login |

### 403 Forbidden

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Only the uploader can share` | Not the file owner | Only share your own files |
| `Cannot share with users outside your class` | Recipient not in same class | Choose recipient from same class |
| `Only the recipient can accept this share` | Not the recipient | Login as recipient user |
| `Only the recipient can reject this share` | Not the recipient | Login as recipient user |
| `Share must be accepted before downloading` | Trying to download pending/rejected share | Accept the share first |
| `You are not authorized to download this file` | Not the recipient | Can only download your own shares |
| `Don't have permission to share` | Permission check failed | Ensure file ownership and class membership |

### 404 Not Found

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Share not found` | Invalid share_id or not involved in share | Check share_id and permissions |
| `This file has been deleted by the owner` | File owner deleted the original | Cannot download deleted files |
| `File not found on server` | File missing from storage | Contact administrator |

---

## Architecture Notes

### Service Layer Pattern

Business logic is separated into `SharingService` class with static methods:

- **Permission Checks**: `can_share_file()`, `can_receive_share()`
- **Queries**: `get_shared_with_me()`, `get_my_shares()`, `get_pending_requests()`
- **CRUD**: `create_share()`, `bulk_share()`, `share_exists()`

### Query Optimization

All queries use:
- `select_related()` for foreign keys (upload, shared_by, shared_with)
- `prefetch_related()` for reverse relationships
- Indexes on commonly filtered fields (status, shared_at, shared_with)

### Soft Delete Integration

The system respects soft deletes:
- Deleted users cannot share or receive
- Deleted files cannot be shared
- `can_access_file` property checks file deletion status

---

## Related Documentation

- **Authentication**: See [authentication/README.md](../authentication/README.md)
- **File Uploads**: See [uploads/README.md](../uploads/README.md)
- **Classes**: See [classes/README.md](../classes/README.md)

---

## Future Enhancements

Potential features for future development:

1. **Share Expiry**: Time-limited shares
2. **Share Revocation**: Owner can revoke accepted shares
3. **Share Notifications**: Real-time notifications when shares are created/accepted
4. **Share Statistics**: Track share counts, popular files
5. **Share Comments**: Recipients can comment on shared files
6. **Share Permissions**: Read-only vs download permissions
7. **Share Groups**: Share with entire class at once

---

**Last Updated**: January 2024  
**Version**: 1.0  
**Maintainer**: Kibegi Development Team
