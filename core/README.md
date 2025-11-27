# Core App

Cross-cutting functionality for the Kibegi platform, including global search and utilities.

## Table of Contents

- [Overview](#overview)
- [Global Search](#global-search)
- [API Endpoints](#api-endpoints)
- [Testing Guide](#testing-guide)
- [Architecture](#architecture)

---

## Overview

The core app provides shared functionality used across all Kibegi apps:

- **Global Search**: Search across users, classes, files, and friends
- **Response Utilities**: Standardized API responses
- **Pagination**: Consistent pagination across all endpoints
- **Code Generator**: Unique code generation for classes, files, etc.
- **Request Logging**: HTTP request/response logging

---

## Global Search

Search across all Kibegi apps in a single query.

### Features

- **Multi-App Search**: Search users, classes, files, and friends simultaneously
- **Permission-Aware**: Results respect user permissions
- **Categorized Results**: Results grouped by type
- **Configurable Limits**: Control results per category
- **Category Filtering**: Search specific categories only

### Searchable Categories

| Category | Searches By | Permissions |
|----------|------------|-------------|
| `users` | Email, full name | All active users (except self) |
| `classes` | Name, description, code | Member classes + public classes |
| `files` | Filename | Own uploads + accepted shared files |
| `friends` | Friend's name, email | Accepted friendships only |

---

## API Endpoints

### Global Search

**GET** `/api/v1/search/`

Search across all apps.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query (min 2 chars) |
| `limit` | integer | No | 10 | Max results per category (1-50) |
| `categories` | string | No | all | Comma-separated: `users,classes,files,friends` |

#### Example Requests

```bash
# Search everything for "john"
GET /api/v1/search/?q=john

# Search with limit
GET /api/v1/search/?q=john&limit=5

# Search specific categories
GET /api/v1/search/?q=john&categories=users,friends

# Search only classes
GET /api/v1/search/?q=python&categories=classes
```

#### Success Response (200)

```json
{
    "success": true,
    "message": "Found 12 result(s) for 'john'",
    "data": {
        "query": "john",
        "total_results": 12,
        "results": {
            "users": [
                {
                    "id": "uuid-1",
                    "type": "user",
                    "email": "john@example.com",
                    "full_name": "John Doe",
                    "user_type": "student"
                }
            ],
            "classes": [
                {
                    "id": "uuid-2",
                    "type": "class",
                    "name": "John's Study Group",
                    "description": "A collaborative study group for...",
                    "class_code": "ABC123",
                    "is_verified": false,
                    "member_count": 8,
                    "creator_name": "John Doe"
                }
            ],
            "files": [
                {
                    "id": "uuid-3",
                    "type": "file",
                    "file_name": "john_lecture_notes.pdf",
                    "file_type": "document",
                    "file_size": 2048576,
                    "file_code": "XYZ789",
                    "uploader_name": "John Doe",
                    "class_name": "CS 101",
                    "is_own": true,
                    "created_at": "2025-11-25T10:00:00Z"
                }
            ],
            "friends": [
                {
                    "id": "15",
                    "type": "friend",
                    "friend_id": "uuid-4",
                    "friend_email": "johnny@example.com",
                    "friend_name": "Johnny Smith",
                    "friend_type": "lecturer",
                    "nickname": "Johnny Boy",
                    "accepted_at": "2025-11-20T15:30:00Z"
                }
            ]
        },
        "counts": {
            "users": 3,
            "classes": 2,
            "files": 4,
            "friends": 3
        }
    }
}
```

#### Error Responses

**400 Bad Request** - Query too short:
```json
{
    "success": false,
    "message": "Search query must be at least 2 characters",
    "data": null,
    "errors": {
        "q": ["Ensure this field has at least 2 characters."]
    }
}
```

**401 Unauthorized** - Not authenticated:
```json
{
    "success": false,
    "message": "Authentication credentials were not provided.",
    "data": null
}
```

---

## Testing Guide

### Using Swagger UI

1. Navigate to: `http://localhost:8000/api/docs/`
2. Authenticate with your access token
3. Find **Search** tag
4. Use the **Global Search** endpoint

### Using cURL

```bash
# Get access token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "password"}' \
  | jq -r '.data.tokens.access')

# Search all categories
curl -X GET "http://localhost:8000/api/v1/search/?q=john" \
  -H "Authorization: Bearer $TOKEN" | jq

# Search specific categories
curl -X GET "http://localhost:8000/api/v1/search/?q=python&categories=classes,files&limit=5" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Test Scenarios

#### Scenario 1: Multi-Category Search

1. Search for a common term like a user's name
2. Verify results appear in multiple categories
3. Check that results respect permissions

#### Scenario 2: Category Filtering

1. Search with `categories=users`
2. Verify only user results returned
3. Other categories should be empty or missing

#### Scenario 3: Permission Verification

1. Search for a class you're not a member of
2. Verify it doesn't appear (unless public)
3. Search for a file someone shared with you
4. Verify it appears if share was accepted

---

## Architecture

### Service Layer

The `GlobalSearchService` handles all search logic:

```python
from core.services import GlobalSearchService

# Basic search
results = GlobalSearchService.search(
    query="john",
    user=request.user,
    limit=10,
    categories=['users', 'friends']
)
```

### Internal Methods

| Method | Description |
|--------|-------------|
| `_search_users()` | Search users by email/name |
| `_search_classes()` | Search classes by name/description/code |
| `_search_files()` | Search files by filename |
| `_search_friends()` | Search friends by name/email |

### Logging

All search operations are logged:

```
INFO  Global search initiated by user@example.com: query='john'
DEBUG Searching users for: 'john'
DEBUG Searching classes for: 'john'
DEBUG Searching files for: 'john'
DEBUG Searching friends for: 'john'
INFO  Global search completed: query='john', total_results=12
```

### Response Format

All results follow a consistent structure:

```python
{
    "id": str,           # Unique identifier
    "type": str,         # Category type (user, class, file, friend)
    # ... type-specific fields
}
```

---

## File Structure

```
core/
├── __init__.py
├── admin.py              # Admin configuration
├── apps.py               # App configuration
├── models.py             # RequestLog model
├── pagination.py         # StandardResultsSetPagination
├── permissions.py        # Custom permissions
├── serializers.py        # Search serializers
├── services.py           # GlobalSearchService
├── urls.py               # URL routing
├── views.py              # GlobalSearchAPIView
├── README.md             # This file
└── utils/
    ├── __init__.py
    ├── code_generator.py # Unique code generation
    ├── responses.py      # success_response, error_response
    └── validators.py     # Custom validators
```

---

## Related Documentation

- [Authentication README](../authentication/README.md)
- [Classes README](../classes/README.md)
- [Uploads README](../uploads/README.md)
- [Friends README](../friends/README.md)

---

**Last Updated**: November 2025  
**Version**: 1.0  
**Maintainer**: Kibegi Development Team

