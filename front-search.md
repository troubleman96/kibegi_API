**Overview**

- **Goal:** Describe the search app — its three endpoints, the data each returns, and how to wire them into the frontend (search bar, autocomplete dropdown, history panel).
- **Scope:** API surface, request/response shapes, category filtering, search history, and where the code lives.

---

**Search App — what it is and how it works**

- **Purpose:** Dedicated search app that lets authenticated users query across users, classes, uploaded files, friends, and the public library in a single request. Every full search is recorded in the user's search history. Autocomplete runs separately and never writes history.
- **Key model:**
  - `SearchHistory`: one row per search — `query`, `result_count`, `categories_searched` (JSON list), `created_at`, FK to user. Table: `search_searchhistory`. See models.py.
- **Service:** `SearchService` in services.py. Methods:
  - `search(query, user, limit, categories)` — runs all five category handlers, saves history, returns results dict.
  - `suggestions(query, user, limit)` — prefix-only match across users, classes, and library; no history written.
- **App location:** `apps/search/` — models, services, serializers, views, urls, migrations all live here.

---

**Endpoints**

**1. Global search**

```
GET /api/v1/search/
Authorization: Bearer <token>
```

Query params:

| Param | Required | Default | Notes |
|---|---|---|---|
| `q` | yes | — | Min 2 chars |
| `limit` | no | 10 | Max results per category, capped at 50 |
| `categories` | no | all | Comma-separated: `users,classes,files,friends,library` |

Example requests:
```
GET /api/v1/search/?q=calculus
GET /api/v1/search/?q=john&limit=5&categories=users,friends
GET /api/v1/search/?q=math&categories=library
```

Response `200 OK`:
```json
{
  "success": true,
  "message": "Found 6 result(s) for 'calculus'",
  "data": {
    "query": "calculus",
    "total_results": 6,
    "results": {
      "users": [],
      "classes": [
        {
          "id": "uuid",
          "type": "class",
          "name": "Calculus 101",
          "description": "Introduction to...",
          "class_code": "CAL101",
          "is_verified": false,
          "member_count": 24,
          "creator_name": "Dr. Jane Doe"
        }
      ],
      "files": [],
      "friends": [],
      "library": [
        {
          "id": "uuid",
          "type": "library",
          "item_code": "ABCD1234",
          "title": "Calculus Past Papers 2023",
          "description": "Collection of...",
          "file_type": "past_paper",
          "subject": "Mathematics",
          "course_code": "MAT201",
          "author_name": "Prof. Smith",
          "category_name": "Mathematics",
          "is_featured": true,
          "view_count": 120,
          "download_count": 45
        }
      ]
    },
    "counts": {
      "users": 0,
      "classes": 1,
      "files": 0,
      "friends": 0,
      "library": 5
    }
  },
  "errors": null
}
```

Response `400` — query missing or too short:
```json
{
  "success": false,
  "message": "Search query must be at least 2 characters",
  "data": null,
  "errors": { "q": ["Ensure this field has at least 2 characters."] }
}
```

**Permission rules per category:**
- `users` — all active users except the caller
- `classes` — classes the caller is a member of OR public classes
- `files` — caller's own uploads OR files shared with them (accepted)
- `friends` — accepted friendships only
- `library` — all public library items (no auth restriction on content)

---

**2. Autocomplete suggestions**

Fast prefix match for the search input dropdown. Does not save history. Call this on every keystroke (debounced ~250 ms).

```
GET /api/v1/search/suggestions/
Authorization: Bearer <token>
```

Query params:

| Param | Required | Default | Notes |
|---|---|---|---|
| `q` | yes | — | Min 1 char |
| `limit` | no | 5 | Capped at 10 |

Example request:
```
GET /api/v1/search/suggestions/?q=cal
```

Response `200 OK`:
```json
{
  "success": true,
  "message": "3 suggestion(s)",
  "data": [
    { "type": "user",    "label": "Calvin Mutiso",       "sub": "calvin@example.com" },
    { "type": "class",   "label": "Calculus 101",         "sub": "CAL101" },
    { "type": "library", "label": "Calculus Past Papers", "sub": "past_paper" }
  ],
  "errors": null
}
```

Each suggestion: `type` (`user` | `class` | `library`), `label` (display name), `sub` (secondary line — email, class code, or file type).

---

**3. Search history**

```
GET    /api/v1/search/history/    — 20 most recent searches
DELETE /api/v1/search/history/    — clear all history for the caller
Authorization: Bearer <token>
```

GET response `200 OK`:
```json
{
  "success": true,
  "message": "3 recent search(es)",
  "data": [
    {
      "id": 42,
      "query": "calculus",
      "result_count": 6,
      "categories_searched": ["users", "classes", "files", "friends", "library"],
      "created_at": "2026-05-31T10:23:00Z"
    }
  ],
  "errors": null
}
```

DELETE response `200 OK`:
```json
{
  "success": true,
  "message": "Cleared 3 search record(s)",
  "data": null,
  "errors": null
}
```

---

**Frontend integration patterns**

- **Global search bar:** debounce the input at ~300 ms. Under 2 chars → hit suggestions endpoint. At 2+ chars on Enter or explicit search action → hit the full search endpoint.
- **Autocomplete dropdown:** call `/suggestions/` on every keystroke (debounced ~250 ms, min 1 char). Render grouped by `type`. On click → trigger full search with the selected label as `q`.
- **Category tabs / filters:** pass `categories=library` (or any comma list) to scope results. Keep the active tab in URL params so search results are deep-linkable.
- **Search history panel:** load `/history/` on focus of the search input (when `q` is empty). Show recent queries as chips. Provide a "Clear history" button that calls `DELETE /history/`.
- **Result cards by type:**
  - `user` → avatar + full_name + user_type badge
  - `class` → class name + class_code chip + member count
  - `file` → filename + file_type icon + uploader name + "Shared" tag if `is_own = false`
  - `friend` → avatar + friend_name + nickname (if set)
  - `library` → title + file_type badge + subject + download count + featured star if `is_featured`

---

**Typical request flow**

1. User types "math" in search bar.
2. Frontend debounces → `GET /api/v1/search/suggestions/?q=math` → renders dropdown.
3. User presses Enter → `GET /api/v1/search/?q=math` → renders full results page.
4. Backend `SearchService.search()` fans out to 5 category queries, saves a `SearchHistory` row, returns merged dict.
5. User clicks a category tab "Library" → `GET /api/v1/search/?q=math&categories=library` → renders library-only results.
6. User opens search bar later with empty input → `GET /api/v1/search/history/` → recent searches shown as chips.

---

**Where to look in the code**

- Service logic: services.py
- Models: models.py
- Serializers: serializers.py
- Views: views.py
- Routes: urls.py and urls.py (main router)
- Migration: 0001_initial.py
- Admin: admin.py
