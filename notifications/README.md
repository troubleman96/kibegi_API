# Notifications System

Real-time notification system for the Kibegi platform, keeping users informed about important events and actions.

## Table of Contents
- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Notification Types](#notification-types)
- [Integration Guide](#integration-guide)
- [Testing Guide](#testing-guide)
- [Common Errors](#common-errors)

---

## Overview

The notifications system provides real-time alerts for:
- File sharing requests and updates
- Friend requests and acceptances
- Class invitations and updates
- System announcements

### Key Features

- **Multiple Notification Types**: Share requests, friend requests, file shared alerts
- **Read/Unread Tracking**: Mark individual or all notifications as read
- **Filtering**: Filter by read status and notification type
- **Pagination**: Efficient handling of large notification lists
- **Related Objects**: Link notifications to specific shares, friendships, etc.
- **Auto-cleanup**: Optional cleanup of old notifications

---

## Models

### Notification

Represents a notification sent to a user.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `user` | ForeignKey | User receiving the notification |
| `notification_type` | CharField | Type: `share_request`, `friend_request`, `file_shared` |
| `content` | TextField | Human-readable notification message |
| `related_object_id` | CharField | ID of related object (share ID, friendship ID, etc.) |
| `is_read` | Boolean | Whether notification has been read (default: False) |
| `created_at` | DateTimeField | When notification was created |

#### Constraints

- **Index on**: `['user', 'is_read']` - For filtering unread notifications
- **Index on**: `['user', '-created_at']` - For user's notification list

#### Model Methods

```python
def mark_as_read():
    """Mark notification as read"""
    
def __str__() -> str:
    """String representation with user, type, and status"""
```

---

## API Endpoints

All endpoints require authentication. Base path: `/api/v1/notifications/`

### 1. List Notifications

**GET** `/api/v1/notifications/`

Get paginated list of notifications with optional filters.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `is_read` | string | Filter by status: `true`, `false`, or `all` (default: `all`) |
| `type` | string | Filter by type: `share_request`, `friend_request`, `file_shared` |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

#### Example Requests

```bash
# Get all notifications (paginated)
GET /api/v1/notifications/

# Get only unread notifications
GET /api/v1/notifications/?is_read=false

# Get only share request notifications
GET /api/v1/notifications/?type=share_request

# Get read friend request notifications, page 2
GET /api/v1/notifications/?is_read=true&type=friend_request&page=2
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Retrieved 15 notifications",
    "data": {
        "count": 15,
        "next": "http://api/v1/notifications/?page=2",
        "previous": null,
        "unread_count": 5,
        "results": [
            {
                "id": 101,
                "notification_type": "share_request",
                "content": "John Doe shared 'Assignment.pdf' with you",
                "related_object_id": "42",
                "is_read": false,
                "created_at": "2024-01-15T10:30:00Z"
            },
            {
                "id": 100,
                "notification_type": "friend_request",
                "content": "Jane Smith sent you a friend request",
                "related_object_id": "25",
                "is_read": false,
                "created_at": "2024-01-15T09:15:00Z"
            },
            {
                "id": 99,
                "notification_type": "file_shared",
                "content": "Mike Johnson accepted your share of 'Notes.pdf'",
                "related_object_id": "38",
                "is_read": true,
                "created_at": "2024-01-14T16:45:00Z"
            }
        ]
    }
}
```

---

### 2. Mark Notification as Read

**POST** `/api/v1/notifications/{notification_id}/read/`

Mark a specific notification as read.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `notification_id` | integer | ID of the notification to mark as read |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Notification marked as read",
    "data": {
        "id": 101,
        "notification_type": "share_request",
        "content": "John Doe shared 'Assignment.pdf' with you",
        "related_object_id": "42",
        "is_read": true,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

#### Error Responses

- `400`: Notification already marked as read
- `404`: Notification not found

---

### 3. Mark All Notifications as Read

**POST** `/api/v1/notifications/read-all/`

Mark all unread notifications for the authenticated user as read.

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Marked 5 notifications as read",
    "data": {
        "marked_read": 5
    }
}
```

---

### 4. Delete Notification

**DELETE** `/api/v1/notifications/{notification_id}/`

Delete a specific notification.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `notification_id` | integer | ID of the notification to delete |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Notification deleted successfully"
}
```

#### Error Responses

- `404`: Notification not found

---

## Notification Types

### Share Request

**Type**: `share_request`

**Triggered When**: Someone shares a file with you

**Content Format**: `"{Sharer Name} shared '{Filename}' with you"`

**Related Object**: Share ID

**Example**:
```json
{
    "notification_type": "share_request",
    "content": "John Doe shared 'Assignment.pdf' with you",
    "related_object_id": "42"
}
```

### Friend Request

**Type**: `friend_request`

**Triggered When**: Someone sends you a friend request

**Content Format**: `"{Requester Name} sent you a friend request"`

**Related Object**: Friendship ID

**Example**:
```json
{
    "notification_type": "friend_request",
    "content": "Jane Smith sent you a friend request",
    "related_object_id": "25"
}
```

### File Shared

**Type**: `file_shared`

**Triggered When**: Someone accepts your share

**Content Format**: `"{Accepter Name} accepted your share of '{Filename}'"`

**Related Object**: Share ID

**Example**:
```json
{
    "notification_type": "file_shared",
    "content": "Mike Johnson accepted your share of 'Notes.pdf'",
    "related_object_id": "38"
}
```

---

## Integration Guide

### Creating Notifications

Use the `NotificationService` to create notifications from other apps:

#### From Sharing App

```python
from notifications.services import NotificationService

# When a file is shared
NotificationService.create_notification(
    user=recipient_user,
    notification_type='share_request',
    content=f"{sharer.full_name} shared '{upload.original_filename}' with you",
    related_id=str(share.id)
)

# When a share is accepted
NotificationService.create_notification(
    user=share.shared_by,
    notification_type='file_shared',
    content=f"{accepter.full_name} accepted your share of '{share.upload.original_filename}'",
    related_id=str(share.id)
)
```

#### From Friends App

```python
from notifications.services import NotificationService

# When a friend request is sent
NotificationService.create_notification(
    user=recipient_user,
    notification_type='friend_request',
    content=f"{sender.full_name} sent you a friend request",
    related_id=str(friendship.id)
)
```

### Example Integration in Views

```python
# In sharing/views.py
from notifications.services import NotificationService

class ShareFileAPIView(APIView):
    def post(self, request):
        # ... share logic ...
        
        # Create notification for recipient
        NotificationService.create_notification(
            user=recipient,
            notification_type='share_request',
            content=f"{request.user.full_name} shared '{upload.original_filename}' with you",
            related_id=str(share.id)
        )
        
        return success_response(...)
```

### Querying Notifications

```python
from notifications.services import NotificationService

# Get all unread notifications
unread = NotificationService.get_user_notifications(
    user=request.user,
    is_read=False
)

# Get unread count
count = NotificationService.get_unread_count(request.user)

# Get specific type
friend_requests = NotificationService.get_user_notifications(
    user=request.user,
    notification_type='friend_request',
    is_read=False
)
```

---

## Testing Guide

### Using Swagger UI

1. **Navigate to Swagger**
   ```
   http://localhost:8000/api/schema/swagger-ui/
   ```

2. **Authenticate**
   - Login at `/api/v1/auth/login/`
   - Copy the `access` token
   - Click "Authorize" button
   - Enter: `Bearer YOUR_ACCESS_TOKEN`
   - Click "Authorize"

3. **Test Flow**

   **Step 1: Trigger a notification** (by sharing a file or sending friend request)
   ```
   POST /api/v1/sharing/share/
   Body: {"upload_id": 1, "shared_with_id": 2}
   ```

   **Step 2: List notifications**
   ```
   GET /api/v1/notifications/?is_read=false
   ```

   **Step 3: Mark notification as read**
   ```
   POST /api/v1/notifications/{notification_id}/read/
   ```

   **Step 4: Verify unread count decreased**
   ```
   GET /api/v1/notifications/
   # Check unread_count in response
   ```

   **Step 5: Mark all as read**
   ```
   POST /api/v1/notifications/read-all/
   ```

   **Step 6: Delete a notification**
   ```
   DELETE /api/v1/notifications/{notification_id}/
   ```

### Using cURL

#### 1. Login
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}' \
  | jq -r '.data.access')
```

#### 2. List All Notifications
```bash
curl -X GET http://localhost:8000/api/v1/notifications/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 3. List Unread Notifications
```bash
curl -X GET "http://localhost:8000/api/v1/notifications/?is_read=false" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 4. Filter by Type
```bash
curl -X GET "http://localhost:8000/api/v1/notifications/?type=share_request" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 5. Mark Notification as Read
```bash
NOTIFICATION_ID=101
curl -X POST http://localhost:8000/api/v1/notifications/$NOTIFICATION_ID/read/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 6. Mark All as Read
```bash
curl -X POST http://localhost:8000/api/v1/notifications/read-all/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 7. Delete Notification
```bash
NOTIFICATION_ID=101
curl -X DELETE http://localhost:8000/api/v1/notifications/$NOTIFICATION_ID/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Manual Testing Script

Create a Python script to test notifications:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(
    f"{BASE_URL}/api/v1/auth/login/",
    json={"email": "your@email.com", "password": "yourpassword"}
)
token = response.json()['data']['access']
headers = {"Authorization": f"Bearer {token}"}

# 1. Trigger notification (share a file)
print("1. Sharing a file to trigger notification...")
response = requests.post(
    f"{BASE_URL}/api/v1/sharing/share/",
    headers=headers,
    json={"upload_id": 1, "shared_with_id": 2}
)
print(json.dumps(response.json(), indent=2))

# 2. List unread notifications
print("\n2. Listing unread notifications...")
response = requests.get(
    f"{BASE_URL}/api/v1/notifications/?is_read=false",
    headers=headers
)
data = response.json()
print(f"Unread count: {data['data']['unread_count']}")
print(json.dumps(data, indent=2))

# 3. Mark first notification as read
if data['data']['results']:
    notification_id = data['data']['results'][0]['id']
    print(f"\n3. Marking notification {notification_id} as read...")
    response = requests.post(
        f"{BASE_URL}/api/v1/notifications/{notification_id}/read/",
        headers=headers
    )
    print(json.dumps(response.json(), indent=2))

# 4. Mark all as read
print("\n4. Marking all notifications as read...")
response = requests.post(
    f"{BASE_URL}/api/v1/notifications/read-all/",
    headers=headers
)
print(json.dumps(response.json(), indent=2))

# 5. List all notifications
print("\n5. Listing all notifications...")
response = requests.get(
    f"{BASE_URL}/api/v1/notifications/",
    headers=headers
)
print(json.dumps(response.json(), indent=2))
```

### Testing Scenarios

#### Scenario 1: Share Notification Flow

1. User A shares file with User B
2. User B receives `share_request` notification
3. User B lists notifications → Sees share request
4. User B marks notification as read
5. User B accepts the share
6. User A receives `file_shared` notification

#### Scenario 2: Friend Request Flow

1. User A sends friend request to User B
2. User B receives `friend_request` notification
3. User B lists unread notifications → Sees request
4. User B marks notification as read
5. User B accepts friend request
6. Notification still visible in read notifications

#### Scenario 3: Notification Management

1. User has 10 unread notifications
2. User marks 3 individually as read
3. Unread count drops to 7
4. User clicks "Mark all as read"
5. All 7 remaining marked as read
6. Unread count becomes 0

#### Scenario 4: Filtering and Pagination

1. User has 50 total notifications
2. User filters by `is_read=false` → 20 results
3. User filters by `type=share_request` → 15 results
4. User combines filters → 5 results
5. User paginate through results (20 per page)

---

## Common Errors

### 400 Bad Request

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Notification already marked as read` | Trying to mark read notification | Check `is_read` status first |
| `Invalid notification type` | Wrong type in filter | Use: share_request, friend_request, file_shared |

### 401 Unauthorized

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Authentication credentials were not provided` | Missing token | Include `Authorization: Bearer <token>` |
| `Given token not valid` | Expired/invalid token | Login again |

### 404 Not Found

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Notification not found` | Invalid notification_id or not yours | Check ID and ownership |

---

## Best Practices

### For Frontend Developers

1. **Poll for new notifications** every 30-60 seconds:
   ```javascript
   setInterval(() => {
       fetch('/api/v1/notifications/?is_read=false')
           .then(res => res.json())
           .then(data => {
               updateNotificationBadge(data.data.unread_count);
           });
   }, 30000); // 30 seconds
   ```

2. **Show unread count** in navigation:
   ```javascript
   const unreadCount = response.data.unread_count;
   badgeElement.textContent = unreadCount > 0 ? unreadCount : '';
   ```

3. **Mark as read on click**:
   ```javascript
   notificationElement.addEventListener('click', async () => {
       await fetch(`/api/v1/notifications/${id}/read/`, {
           method: 'POST',
           headers: { 'Authorization': `Bearer ${token}` }
       });
       updateUI();
   });
   ```

4. **Handle related objects**:
   ```javascript
   notification.addEventListener('click', () => {
       const type = notification.notification_type;
       const id = notification.related_object_id;
       
       if (type === 'share_request') {
           navigateTo(`/shares/${id}`);
       } else if (type === 'friend_request') {
           navigateTo(`/friends/requests`);
       }
   });
   ```

### For Backend Developers

1. **Always create notifications** for user actions:
   ```python
   # Good
   share = Share.objects.create(...)
   NotificationService.create_notification(...)
   
   # Bad - missing notification
   share = Share.objects.create(...)
   ```

2. **Use descriptive content**:
   ```python
   # Good
   content = f"{user.full_name} shared '{filename}' with you"
   
   # Bad
   content = "You have a new share"
   ```

3. **Include related object IDs**:
   ```python
   # Good
   NotificationService.create_notification(
       user=recipient,
       notification_type='share_request',
       content=content,
       related_id=str(share.id)  # Important!
   )
   ```

4. **Clean up old notifications** (optional cron job):
   ```python
   from datetime import timedelta
   from django.utils import timezone
   
   # Delete read notifications older than 30 days
   old_date = timezone.now() - timedelta(days=30)
   Notification.objects.filter(
       is_read=True,
       created_at__lt=old_date
   ).delete()
   ```

---

## Architecture Notes

### Service Layer Pattern

All business logic is in `NotificationService`:
- `create_notification()` - Create with validation
- `get_user_notifications()` - Retrieve with filters
- `mark_as_read()` - Single notification
- `mark_all_as_read()` - Bulk update
- `get_unread_count()` - Count unread
- `delete_notification()` - Remove notification

### Query Optimization

All queries use:
- Indexes on `(user, is_read)` and `(user, -created_at)`
- Filtering at database level
- Pagination for large result sets
- No N+1 queries

### Permissions

- Users can only see their own notifications
- Users can only mark their own notifications as read
- Users can only delete their own notifications
- No admin required for notification management

---

## Future Enhancements

Potential features for future development:

1. **WebSocket Support**: Real-time push notifications via WebSockets
2. **Email Notifications**: Send emails for important notifications
3. **Push Notifications**: Mobile push via FCM/APNs
4. **Notification Preferences**: User settings for notification types
5. **Notification Groups**: Group similar notifications together
6. **Action Buttons**: Quick actions in notification (Accept, Reject)
7. **Rich Content**: Support for images, links, and formatting
8. **Notification History**: Separate archive for old notifications
9. **Mute Options**: Temporarily mute certain notification types
10. **Batch Operations**: Delete multiple notifications at once

---

## Related Documentation

- **Authentication**: See [authentication/README.md](../authentication/README.md)
- **File Sharing**: See [sharing/README.md](../sharing/README.md)
- **Friends**: See [friends/README.md](../friends/README.md)
- **Classes**: See [classes/README.md](../classes/README.md)

---

**Last Updated**: November 2024  
**Version**: 1.0  
**Maintainer**: Kibegi Development Team
