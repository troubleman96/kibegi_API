# Friends System

Complete friend management system for the Kibegi platform, enabling users to connect with classmates and build their network.

## Table of Contents
- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Request/Accept Flow](#requestaccept-flow)
- [Testing Guide](#testing-guide)
- [Common Errors](#common-errors)

---

## Overview

The friends system allows users to:
- Search for other users by email or name
- Send friend requests
- Accept or reject friend requests
- Set custom nicknames for friends
- Remove friends

### Key Features

- **Bi-directional Friendships**: Both users become friends when request is accepted
- **Request/Accept Pattern**: Must accept before becoming friends
- **Custom Nicknames**: Set personal names for your friends
- **User Search**: Find users by email or full name
- **Status Tracking**: pending or accepted states
- **Duplicate Prevention**: Can't send multiple requests to same user

---

## Models

### Friendship

Represents a friend relationship between two users.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `user` | ForeignKey | User who sent the friend request |
| `friend` | ForeignKey | User who received the request |
| `nickname` | CharField | Optional custom name for the friend (max 100 chars) |
| `status` | CharField | Current status: `pending` or `accepted` |
| `created_at` | DateTimeField | When request was sent |
| `accepted_at` | DateTimeField | When request was accepted (null if pending) |

#### Constraints

- **unique_together**: `['user', 'friend']` - Prevents duplicate friendships
- **Index on**: `['user', 'status']` - For efficient filtering
- **Index on**: `['friend', 'status']` - For request queries

#### Model Methods

```python
def accept():
    """Accept a pending friend request"""
    
def is_pending() -> bool:
    """Check if friendship is pending"""
    
def is_accepted() -> bool:
    """Check if friendship is accepted"""

@property
def display_name() -> str:
    """Get nickname if set, otherwise friend's full name"""
```

---

## API Endpoints

All endpoints require authentication. Base path: `/api/v1/friends/`

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all friends |
| GET | `/search/?q=` | Search users |
| GET | `/requests/incoming/` | List incoming friend requests |
| GET | `/requests/sent/` | List sent friend requests |
| POST | `/add/` | Send friend request |
| POST | `/{id}/accept/` | Accept friend request |
| POST | `/{id}/decline/` | Decline friend request |
| POST | `/{id}/cancel/` | Cancel sent request |
| PATCH | `/{id}/nickname/` | Update friend nickname |
| DELETE | `/{id}/` | Remove friend |

---

### 1. List Friends

**GET** `/api/v1/friends/`

Get list of friends with optional status filter.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `accepted`, or `all` (default: `accepted`) |

#### Example Requests

```bash
# Get all accepted friends
GET /api/v1/friends/

# Get pending friend requests
GET /api/v1/friends/?status=pending

# Get all friendships (pending + accepted)
GET /api/v1/friends/?status=all
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Friends list retrieved successfully",
    "data": {
        "count": 5,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": 1,
                "friend_info": {
                    "id": 42,
                    "email": "john@example.com",
                    "full_name": "John Doe",
                    "user_type": "student"
                },
                "nickname": "Johnny",
                "display_name": "Johnny",
                "status": "accepted",
                "created_at": "2024-01-15T10:00:00Z"
            },
            {
                "id": 2,
                "friend_info": {
                    "id": 43,
                    "email": "jane@example.com",
                    "full_name": "Jane Smith",
                    "user_type": "lecturer"
                },
                "nickname": "",
                "display_name": "Jane Smith",
                "status": "accepted",
                "created_at": "2024-01-14T15:30:00Z"
            }
        ]
    }
}
```

---

### 2. List Incoming Friend Requests

**GET** `/api/v1/friends/requests/incoming/`

Get all pending friend requests sent TO you (waiting for your response).

#### Success Response (200)

```json
{
    "success": true,
    "message": "Found 3 incoming friend request(s)",
    "data": [
        {
            "id": 15,
            "sender_id": "uuid-of-sender",
            "sender_email": "alice@example.com",
            "sender_name": "Alice Wonder",
            "sender_type": "student",
            "recipient_id": "uuid-of-you",
            "recipient_email": "you@example.com",
            "recipient_name": "Your Name",
            "recipient_type": "lecturer",
            "status": "pending",
            "created_at": "2025-11-25T10:00:00Z"
        }
    ]
}
```

---

### 3. List Sent Friend Requests

**GET** `/api/v1/friends/requests/sent/`

Get all pending friend requests you have sent (waiting for others to accept).

#### Success Response (200)

```json
{
    "success": true,
    "message": "Found 2 sent friend request(s)",
    "data": [
        {
            "id": 20,
            "sender_id": "uuid-of-you",
            "sender_email": "you@example.com",
            "sender_name": "Your Name",
            "sender_type": "lecturer",
            "recipient_id": "uuid-of-recipient",
            "recipient_email": "bob@example.com",
            "recipient_name": "Bob Builder",
            "recipient_type": "student",
            "status": "pending",
            "created_at": "2025-11-24T15:30:00Z"
        }
    ]
}
```

---

### 4. Send Friend Request

**POST** `/api/v1/friends/add/`

Send a friend request to another user.

#### Request Body

Provide either `user_id` OR `email`:

```json
{
    "user_id": 42,
    "email": "optional@example.com"
}
```

**Option A: By User ID**
```json
{
    "user_id": 42
}
```

**Option B: By Email**
```json
{
    "email": "john@example.com"
}
```

#### Success Response (201)

```json
{
    "success": true,
    "message": "Friend request sent successfully",
    "data": {
        "id": 10,
        "user": 1,
        "user_email": "me@example.com",
        "user_name": "My Name",
        "friend": 42,
        "friend_email": "john@example.com",
        "friend_name": "John Doe",
        "nickname": "",
        "display_name": "John Doe",
        "status": "pending",
        "created_at": "2024-01-15T11:00:00Z",
        "accepted_at": null
    }
}
```

#### Error Responses

- `400`: Cannot send to yourself, or friendship already exists
- `404`: User not found

---

### 5. Search Users

**GET** `/api/v1/friends/search/`

Search for users to add as friends.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 2 characters) |

#### Example Request

```bash
GET /api/v1/friends/search/?q=john
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Found 3 users",
    "data": [
        {
            "id": 42,
            "email": "john@example.com",
            "full_name": "John Doe",
            "user_type": "student"
        },
        {
            "id": 45,
            "email": "johnny@example.com",
            "full_name": "Johnny Smith",
            "user_type": "lecturer"
        },
        {
            "id": 50,
            "email": "johnson@example.com",
            "full_name": "Mike Johnson",
            "user_type": "student"
        }
    ]
}
```

#### Error Responses

- `400`: Search query too short (less than 2 characters)

---

### 6. Accept Friend Request

**POST** `/api/v1/friends/{friendship_id}/accept/`

Accept a pending friend request sent to you.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `friendship_id` | integer | ID of the friendship to accept |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Friend request accepted",
    "data": {
        "id": 10,
        "user": 42,
        "user_email": "john@example.com",
        "user_name": "John Doe",
        "friend": 1,
        "friend_email": "me@example.com",
        "friend_name": "My Name",
        "nickname": "",
        "display_name": "John Doe",
        "status": "accepted",
        "created_at": "2024-01-15T10:00:00Z",
        "accepted_at": "2024-01-15T11:30:00Z"
    }
}
```

#### Error Responses

- `400`: Request already accepted
- `403`: You can only accept requests sent to you
- `404`: Friend request not found

---

### 7. Decline Friend Request

**POST** `/api/v1/friends/{friendship_id}/decline/`

Decline (reject) a pending friend request sent to you. The request will be permanently deleted.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `friendship_id` | integer | ID of the friend request to decline |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Friend request declined successfully"
}
```

#### Error Responses

- `400`: Cannot decline an already accepted friend request
- `403`: You can only decline requests sent to you
- `404`: Friend request not found

---

### 8. Cancel Sent Friend Request

**POST** `/api/v1/friends/{friendship_id}/cancel/`

Cancel a pending friend request that you sent. Use this to withdraw a request before the recipient responds.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `friendship_id` | integer | ID of the friend request to cancel |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Friend request cancelled successfully"
}
```

#### Error Responses

- `400`: Cannot cancel an already accepted friend request
- `403`: You can only cancel requests you sent
- `404`: Friend request not found

---

### 9. Update Friend Nickname

**PATCH** `/api/v1/friends/{friendship_id}/nickname/`

Set or update a custom nickname for your friend.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `friendship_id` | integer | ID of the friendship |

#### Request Body

```json
{
    "nickname": "Johnny"
}
```

**To remove nickname:**
```json
{
    "nickname": ""
}
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Nickname updated successfully",
    "data": {
        "id": 10,
        "user": 1,
        "user_email": "me@example.com",
        "user_name": "My Name",
        "friend": 42,
        "friend_email": "john@example.com",
        "friend_name": "John Doe",
        "nickname": "Johnny",
        "display_name": "Johnny",
        "status": "accepted",
        "created_at": "2024-01-15T10:00:00Z",
        "accepted_at": "2024-01-15T11:30:00Z"
    }
}
```

#### Error Responses

- `400`: Can only set nicknames for accepted friends
- `403`: You can only update nicknames for your own friends
- `404`: Friendship not found

---

### 10. Remove Friend

**DELETE** `/api/v1/friends/{friendship_id}/`

Remove a friend (unfriend) or delete any friendship.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `friendship_id` | integer | ID of the friendship to remove |

#### Request Body

Empty (no body required)

#### Success Response (200)

```json
{
    "success": true,
    "message": "Friend removed successfully"
}
```

#### Error Responses

- `403`: You can only remove your own friends
- `404`: Friendship not found

---

## Request/Accept Flow

### Complete Workflow

```
User A                                User B
   │                                     │
   │──── Send Friend Request ────────►│
   │         (status: pending)          │
   │                                     │
   │                                     │◄─── Receives Request
   │                                     │     (can accept/reject)
   │                                     │
   │◄──── Accept Request ──────────────│
   │    (status: accepted)               │
   │                                     │
   │    Both are now friends! ✓          │
   │    Can set nicknames                │
   │    Can remove friendship            │
```

### Status Transitions

| From | To | Action | Who |
|------|-----|--------|-----|
| - | `pending` | Send request | Sender |
| `pending` | `accepted` | Accept request | Recipient |
| `pending` | (deleted) | Reject/cancel | Either user |
| `accepted` | (deleted) | Remove friend | Either user |

### State Properties

| Status | Can Accept | Can Set Nickname | Can Remove |
|--------|------------|------------------|------------|
| `pending` | ✅ Recipient only | ❌ | ✅ Both users |
| `accepted` | ❌ | ✅ Both users | ✅ Both users |

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

   **Step 1: Search for users**
   ```
   GET /api/v1/friends/search/?q=john
   ```

   **Step 2: Send friend request**
   ```
   POST /api/v1/friends/add/
   Body: {"user_id": 42}
   ```

   **Step 3: Recipient accepts (login as recipient first)**
   ```
   POST /api/v1/friends/{friendship_id}/accept/
   ```

   **Step 4: Set nickname**
   ```
   PATCH /api/v1/friends/{friendship_id}/nickname/
   Body: {"nickname": "Johnny"}
   ```

   **Step 5: View friends list**
   ```
   GET /api/v1/friends/?status=accepted
   ```

### Using cURL

#### 1. Login
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}' \
  | jq -r '.data.access')
```

#### 2. Search Users
```bash
curl -X GET "http://localhost:8000/api/v1/friends/search/?q=john" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 3. Send Friend Request
```bash
curl -X POST http://localhost:8000/api/v1/friends/add/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42}' | jq
```

#### 4. List Friends
```bash
# All accepted friends
curl -X GET http://localhost:8000/api/v1/friends/ \
  -H "Authorization: Bearer $TOKEN" | jq

# Pending requests
curl -X GET "http://localhost:8000/api/v1/friends/?status=pending" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 5. Accept Friend Request
```bash
FRIENDSHIP_ID=10
curl -X POST http://localhost:8000/api/v1/friends/$FRIENDSHIP_ID/accept/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 6. Set Nickname
```bash
FRIENDSHIP_ID=10
curl -X PATCH http://localhost:8000/api/v1/friends/$FRIENDSHIP_ID/nickname/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nickname": "Johnny"}' | jq
```

#### 7. Remove Friend
```bash
FRIENDSHIP_ID=10
curl -X DELETE http://localhost:8000/api/v1/friends/$FRIENDSHIP_ID/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Testing Scenarios

#### Scenario 1: Successful Friendship

1. User A searches for User B → Finds User B
2. User A sends request to User B → Returns pending friendship
3. User B lists requests → Sees User A's request
4. User B accepts request → Status becomes accepted
5. Both users see each other in friends list

#### Scenario 2: Custom Nickname

1. Users are friends (accepted)
2. User A sets nickname "Best Friend" for User B
3. User A's friend list shows "Best Friend" instead of "User B Name"
4. User B's view of User A unchanged (separate nicknames)

#### Scenario 3: Request Management

1. User A sends request to User B
2. User A cancels request (DELETE) → Request removed
3. User B never sees the request

#### Scenario 4: Duplicate Prevention

1. User A sends request to User B → Success
2. User A tries to send again → Error: "Friendship already exists"
3. User B tries to send to User A → Error: "Friendship already exists"

---

## Common Errors

### 400 Bad Request

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Cannot send friend request to yourself` | Trying to add yourself | Choose a different user |
| `Friendship already exists or request pending` | Duplicate request | Check existing friends/requests |
| `Search query must be at least 2 characters` | Query too short | Enter longer search term |
| `Friend request already accepted` | Accepting accepted request | Check status first |
| `Can only set nicknames for accepted friends` | Setting nickname for pending | Wait for acceptance |
| `Either user_id or email must be provided` | Missing both fields | Provide one identifier |

### 401 Unauthorized

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Authentication credentials were not provided` | Missing token | Include `Authorization: Bearer <token>` |
| `Given token not valid` | Expired/invalid token | Login again |

### 403 Forbidden

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `You can only accept requests sent to you` | Not the recipient | Login as correct user |
| `You can only update nicknames for your own friends` | Not your friendship | Check friendship ID |
| `You can only remove your own friends` | Not your friendship | Check friendship ID |

### 404 Not Found

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `User not found` | Invalid user_id or email | Check identifier |
| `Friend request not found` | Invalid friendship_id | Check ID in friends list |
| `Friendship not found` | Invalid friendship_id | Check ID in friends list |

---

## Architecture Notes

### Service Layer Pattern

Business logic is in `FriendService` class:

- **Search**: `search_users()` - Find users by query
- **Validation**: `can_send_request()` - Check permissions
- **Queries**: `get_friends_list()`, `get_friend_requests()`, `get_sent_requests()`
- **Creation**: `create_friend_request()` - Create with validation

### Logging

All friend operations are logged using the `kibegi` logger:

```python
import logging
logger = logging.getLogger('kibegi')
```

**Log Levels:**
- **DEBUG**: Request attempts and query filters
- **INFO**: Successful operations (requests sent, accepted, declined)
- **WARNING**: Failed operations (not found, permission denied)

**Example Log Messages:**
```
INFO  Friend request sent: alice@example.com -> bob@example.com (ID: 15)
INFO  Friend request accepted: alice@example.com <-> bob@example.com (ID: 15)
INFO  Friend request declined: alice@example.com -> bob@example.com (Request ID: 15)
WARN  Decline friend request denied: User charlie@example.com is not the recipient of request 15
```

### Bi-directional Friendships

When User A and User B become friends:
- One `Friendship` record exists: `user=A, friend=B`
- Both users see each other in their friends list
- Nicknames are personal (A's nickname for B ≠ B's nickname for A)

### Query Optimization

All queries use:
- `select_related()` for foreign keys (user, friend)
- Indexes on common filters (status, user+status, friend+status)
- Efficient Q objects for bi-directional queries

---

## Related Documentation

- **Authentication**: See [authentication/README.md](../authentication/README.md)
- **Classes**: See [classes/README.md](../classes/README.md)
- **File Sharing**: See [sharing/README.md](../sharing/README.md)

---

## Future Enhancements

Potential features for future development:

1. **Friend Suggestions**: Suggest mutual friends or classmates
2. **Friend Groups**: Organize friends into categories
3. **Last Seen**: Show when friends were last online
4. **Mutual Friends**: Show common friends
5. **Friend Activity**: See friends' recent uploads or activities
6. **Block Users**: Prevent unwanted friend requests
7. **Friend Limit**: Set maximum number of friends
8. **Bulk Actions**: Accept/remove multiple friends at once

---

**Last Updated**: November 2025  
**Version**: 1.1  
**Maintainer**: Kibegi Development Team
