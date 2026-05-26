# Kibegi — Complete System Documentation

> **Last updated:** 2026-05-26  
> **Covers:** `kibegi_api` (Django REST backend) + `kibegi-your-digital-school-bag` (React frontend)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Software Requirements Specification (SRS)](#2-software-requirements-specification-srs)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Backend — Django API Deep-Dive](#5-backend--django-api-deep-dive)
   - [Project Structure](#51-project-structure)
   - [App Inventory](#52-app-inventory)
   - [URL Routing](#53-url-routing)
   - [Middleware & Settings](#54-middleware--settings)
6. [Database Schema](#6-database-schema)
   - [authentication.User](#61-authenticationuser)
   - [authentication.PasswordResetOTP](#62-authenticationpasswordresetotp)
   - [classes.Class](#63-classesclass)
   - [classes.Membership](#64-classesmembership)
   - [uploads.Upload](#65-uploadsupload)
   - [sharing.SharedFile](#66-sharingsharedfile)
   - [friends.Friendship](#67-friendsfriendship)
   - [notifications.Notification](#68-notificationsnotification)
   - [schedule.ScheduleCalendar](#69-scheduleschedulecalendar)
   - [schedule.ScheduleEvent](#610-schedulescheduleevent)
   - [schedule.ScheduleSyncAccessLog](#611-scheduleschedulesyncaccesslog)
   - [storage.UserStorage](#612-storageuserstorage)
   - [storage.StorageUsageHistory](#613-storageusagehistory)
   - [Entity-Relationship Overview](#614-entity-relationship-overview)
7. [API Endpoints Reference](#7-api-endpoints-reference)
   - [Authentication](#71-authentication)
   - [Classes](#72-classes)
   - [Uploads](#73-uploads)
   - [Files (MinIO/S3)](#74-files-minios3)
   - [Sharing](#75-sharing)
   - [Friends](#76-friends)
   - [Notifications](#77-notifications)
   - [Storage](#78-storage)
   - [Schedule](#79-schedule)
   - [Core / Search](#710-core--search)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
   - [User Registration & OTP Verification](#81-user-registration--otp-verification)
   - [File Upload Flow](#82-file-upload-flow)
   - [File Sharing Flow](#83-file-sharing-flow)
   - [Friend Request Flow](#84-friend-request-flow)
   - [Schedule Sync Flow](#85-schedule-sync-flow)
9. [Frontend — React App Deep-Dive](#9-frontend--react-app-deep-dive)
   - [Project Structure](#91-project-structure)
   - [Routing Map](#92-routing-map)
   - [Context Providers](#93-context-providers)
   - [Service Layer](#94-service-layer)
   - [Component Architecture](#95-component-architecture)
10. [Security Design](#10-security-design)
11. [Storage & File Management](#11-storage--file-management)
12. [Notifications System](#12-notifications-system)
13. [Deployment Architecture](#13-deployment-architecture)
14. [Environment Variables Reference](#14-environment-variables-reference)

---

## 1. Project Overview

**Kibegi** ("Your Digital School Bag") is a full-stack web application designed for students and lecturers to manage their academic digital life in one place.

### What it does

| Feature | Description |
|---------|-------------|
| **Class Management** | Create/join academic classes with a 6-character join code |
| **File Upload & Storage** | Upload study materials into class folders; stored on MinIO/S3 |
| **File Sharing** | Share individual files with friends via a request/accept flow |
| **Friends Network** | Add classmates as friends with a pending/accepted relationship |
| **Schedule / Calendar** | Create calendars (Classes, Exams), add recurring events, export to iCal |
| **Notifications** | Real-time in-app notifications for shares, friend requests, acceptances |
| **Storage Tracking** | Per-user 50 MB quota with byte-accurate tracking |
| **Library / Marketplace** | Browse shared resources (scaffold pages) |
| **Authentication** | Email + JWT, OTP-based email verification, password reset |

### Users

- **Students** — primary consumer; join classes, upload files, share resources
- **Lecturers** — create verified classes, manage membership
- **Admins** — superusers with full Django admin panel access

---

## 2. Software Requirements Specification (SRS)

### 2.1 Functional Requirements

#### Authentication (FR-AUTH)

| ID | Requirement |
|----|-------------|
| FR-AUTH-01 | User shall register with full name, email, password, and user type (student/lecturer) |
| FR-AUTH-02 | System shall send a 6-digit OTP to the user's email upon registration |
| FR-AUTH-03 | User shall verify OTP within 5 minutes (configurable) to activate account |
| FR-AUTH-04 | System shall issue a JWT access token (1 h) and refresh token (7 days) upon successful login |
| FR-AUTH-05 | User shall be able to refresh expired access tokens using a valid refresh token |
| FR-AUTH-06 | System shall blacklist refresh tokens upon logout |
| FR-AUTH-07 | User shall reset password via OTP email with rate-limiting (5 per 25 min) |
| FR-AUTH-08 | User shall update profile picture (image upload, stored in MinIO) |
| FR-AUTH-09 | System shall support username (full name) update via PATCH profile |

#### Class Management (FR-CLASS)

| ID | Requirement |
|----|-------------|
| FR-CLASS-01 | Lecturers and students shall create classes; lecturer classes are marked `is_verified=True` |
| FR-CLASS-02 | System shall auto-generate a unique 6-character alphanumeric class code |
| FR-CLASS-03 | User shall join a class using the class code |
| FR-CLASS-04 | Creator shall be automatically added as a member (lecturer role) |
| FR-CLASS-05 | User shall leave a class; creator cannot leave their own class |
| FR-CLASS-06 | Class creator can delete the class (cascade deletes uploads) |
| FR-CLASS-07 | User shall list all their classes (created + joined) |
| FR-CLASS-08 | User shall view class details including member list |

#### File Upload (FR-UPLOAD)

| ID | Requirement |
|----|-------------|
| FR-UPLOAD-01 | User shall upload files associated with a class they belong to |
| FR-UPLOAD-02 | System shall auto-detect file type from extension and MIME type |
| FR-UPLOAD-03 | System shall enforce the user's 50 MB storage quota before accepting uploads |
| FR-UPLOAD-04 | User shall list their uploads, filter by class or file type |
| FR-UPLOAD-05 | User shall soft-delete files (moved to Trash, retained 21 days) |
| FR-UPLOAD-06 | User shall restore soft-deleted files from Trash |
| FR-UPLOAD-07 | System shall permanently delete files older than 21 days from Trash |
| FR-UPLOAD-08 | User shall search uploads by filename |
| FR-UPLOAD-09 | Files shall be stored on MinIO/S3 with a unique path per user |

#### File Sharing (FR-SHARE)

| ID | Requirement |
|----|-------------|
| FR-SHARE-01 | File owner shall share a file with any registered user |
| FR-SHARE-02 | System shall create a `pending` share request and notify recipient |
| FR-SHARE-03 | Recipient shall accept or reject the share request |
| FR-SHARE-04 | Sharer shall be notified when share is accepted or rejected |
| FR-SHARE-05 | Only accepted shares shall allow file access by recipient |
| FR-SHARE-06 | System shall prevent duplicate shares of the same file to the same user |
| FR-SHARE-07 | User shall view all files shared with them and all files they shared |

#### Friends (FR-FRIEND)

| ID | Requirement |
|----|-------------|
| FR-FRIEND-01 | User shall send friend request to another user |
| FR-FRIEND-02 | Recipient shall accept or decline the request |
| FR-FRIEND-03 | Accepting a request shall notify the sender |
| FR-FRIEND-04 | User shall list all friends and pending requests |
| FR-FRIEND-05 | User shall remove a friend |
| FR-FRIEND-06 | User shall search for users to add as friends |
| FR-FRIEND-07 | User shall assign a custom nickname to a friend |

#### Notifications (FR-NOTIF)

| ID | Requirement |
|----|-------------|
| FR-NOTIF-01 | System shall automatically create notifications for: share_request, share_accepted, share_rejected, friend_request, friend_accepted |
| FR-NOTIF-02 | User shall list all notifications (newest first) |
| FR-NOTIF-03 | User shall mark individual notifications as read |
| FR-NOTIF-04 | User shall mark all notifications as read in one action |
| FR-NOTIF-05 | System shall expose unread notification count |

#### Schedule (FR-SCHED)

| ID | Requirement |
|----|-------------|
| FR-SCHED-01 | System shall auto-create two default calendars for each user: "Classes" and "Examination" |
| FR-SCHED-02 | User shall add events to a calendar with title, start/end time, location, type |
| FR-SCHED-03 | Events shall support recurrence: none, daily, weekly (with days list), monthly |
| FR-SCHED-04 | Each calendar shall have a stable public token for subscription (iCal/ICS) |
| FR-SCHED-05 | User shall share a calendar using a short 6-character code |
| FR-SCHED-06 | Third-party calendar apps shall subscribe via `/api/v1/public/schedule/{token}/subscribe` |
| FR-SCHED-07 | System shall log public sync access for observability |

#### Storage (FR-STORE)

| ID | Requirement |
|----|-------------|
| FR-STORE-01 | Each user shall have a 50 MB default storage quota |
| FR-STORE-02 | System shall update `used_storage_bytes` after every upload or deletion |
| FR-STORE-03 | User shall view storage usage: used MB, free MB, quota MB, usage percentage |
| FR-STORE-04 | System shall block uploads when quota is full |

### 2.2 Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Security** | All API endpoints (except register/login/public schedule) require valid JWT |
| **Performance** | Pagination on all list endpoints (default 20 items/page) |
| **Scalability** | File storage via MinIO/S3 — horizontally scalable |
| **Observability** | All requests logged to rotating file + uploaded to MinIO on rotation |
| **Reliability** | Soft-delete with 21-day retention window prevents accidental data loss |
| **Compatibility** | CORS configured for kibegi.com, localhost:5173 |
| **Documentation** | Swagger UI at `/api/docs/`, ReDoc at `/api/redoc/` |
| **i18n** | Backend uses `gettext_lazy`, Language context in frontend |

---

## 3. System Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                         KIBEGI SYSTEM                             │
│                                                                   │
│  ┌─────────────────────────┐     ┌──────────────────────────────┐│
│  │   FRONTEND (React/Vite) │     │   BACKEND (Django 5.2 / DRF) ││
│  │   kibegi.com            │────▶│   api.kibegi.com             ││
│  │                         │◀────│                              ││
│  │   React 18 + TypeScript │     │   REST API over HTTPS        ││
│  │   TailwindCSS + ShadCN  │     │   JWT Authentication         ││
│  │   React Router v6       │     │   drf-spectacular (Swagger)  ││
│  │   TanStack Query        │     │                              ││
│  │   Axios HTTP client     │     │   ┌──────────────────────┐   ││
│  └─────────────────────────┘     │   │  PostgreSQL / SQLite  │   ││
│                                  │   │  (database)          │   ││
│                                  │   └──────────────────────┘   ││
│                                  │                              ││
│                                  │   ┌──────────────────────┐   ││
│                                  │   │  MinIO / S3          │   ││
│                                  │   │  storage.kibegi.com   │   ││
│                                  │   │  (file storage)      │   ││
│                                  │   └──────────────────────┘   ││
│                                  │                              ││
│                                  │   ┌──────────────────────┐   ││
│                                  │   │  SMTP (Gmail)        │   ││
│                                  │   │  (OTP emails)        │   ││
│                                  │   └──────────────────────┘   ││
│                                  └──────────────────────────────┘│
└───────────────────────────────────────────────────────────────────┘
```

### Communication Pattern

- **Frontend → Backend**: HTTP REST over HTTPS, `Authorization: Bearer <JWT>` header
- **Backend → MinIO**: boto3 SDK (S3-compatible), path-style addressing
- **Backend → Email**: SMTP (configurable; Gmail in production)
- **Backend → Frontend notifications**: Polling (no WebSocket yet; notifications fetched on-demand)

---

## 4. Technology Stack

### Backend (`kibegi_api`)

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Django | 5.2 |
| REST API | Django REST Framework | 3.16 |
| Auth | djangorestframework-simplejwt | — |
| Schema | drf-spectacular (Swagger/OpenAPI 3) | — |
| Database | PostgreSQL (prod) / SQLite (dev) | 12+ / — |
| File Storage | MinIO (S3-compatible) via boto3 | — |
| CORS | django-cors-headers | — |
| Config | python-decouple | — |
| Runtime | Python 3.10+ | — |
| Server | Gunicorn + Nginx | — |

### Frontend (`kibegi-your-digital-school-bag`)

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 18.3 |
| Language | TypeScript | 5.8 |
| Build tool | Vite | 5.4 |
| Styling | TailwindCSS + ShadCN/UI | 3.4 / — |
| UI Components | Radix UI primitives | — |
| Routing | React Router DOM | 6.30 |
| Data fetching | TanStack Query (React Query) | 5.83 |
| HTTP client | Axios | 1.13 |
| Forms | React Hook Form + Zod validation | 7.61 / 3.25 |
| Charts | Recharts | 2.15 |
| Animations | Framer Motion | 12.38 |
| PWA | vite-plugin-pwa + Workbox | — |
| Cookies | js-cookie | 3.0 |
| Deployment | Netlify | — |

---

## 5. Backend — Django API Deep-Dive

### 5.1 Project Structure

```
kibegi_api/                      ← repo root
├── apps/
│   ├── __init__.py
│   ├── authentication/          ← User model, JWT, OTP
│   ├── classes/                 ← Class & Membership models
│   ├── uploads/                 ← Upload model, file CRUD
│   ├── files/                   ← MinIO-aware file download/preview views
│   ├── sharing/                 ← SharedFile model, accept/reject
│   ├── friends/                 ← Friendship model, request/accept
│   ├── notifications/           ← Notification model, mark-read
│   ├── schedule/                ← Calendar & Event models, iCal export
│   ├── storage/                 ← UserStorage model, quota enforcement
│   └── core/                    ← Shared utils, pagination, permissions
│       └── utils/
│           ├── responses.py     ← Standardised API response wrappers
│           ├── validators.py    ← Shared field validators
│           ├── code_generator.py← Unique short-code generation
│           └── log_handler.py   ← MinIO-uploading rotating log handler
├── kibegi_api/
│   ├── settings.py              ← All Django config
│   ├── urls.py                  ← Root URL router
│   ├── middleware.py            ← Request logging middleware
│   ├── asgi.py
│   └── wsgi.py
├── media/                       ← Local media (dev only)
├── logs/                        ← Rotating log files
├── requirements.txt
└── manage.py
```

### 5.2 App Inventory

| App | Status | Purpose |
|-----|--------|---------|
| `core` | ✅ Full | Shared responses, pagination, permissions, search view, management commands |
| `authentication` | ✅ Full | Custom User model, JWT login, OTP registration & password reset |
| `classes` | ✅ Full | Class CRUD, unique join codes, membership management |
| `uploads` | ✅ Full | File upload CRUD, soft-delete, trash, search, storage integration |
| `files` | ✅ Full | MinIO/S3 download, inline preview, metadata endpoints |
| `sharing` | ✅ Full | SharedFile model, share/accept/reject flow, notifications |
| `friends` | ✅ Full | Friendship model, send/accept/remove, user search |
| `notifications` | ✅ Full | Notification model, list, mark-read, unread count |
| `schedule` | ✅ Full | Calendar + Event CRUD, iCal export, public token URLs, QR |
| `storage` | ✅ Full | UserStorage quota tracking, signals, history |

### 5.3 URL Routing

```
/admin/                          ← Django Admin
/api/schema/                     ← OpenAPI schema (JSON)
/api/docs/                       ← Swagger UI
/api/redoc/                      ← ReDoc UI

/api/v1/                         ← Core (search, health)
/api/v1/auth/                    ← Authentication app
/api/v1/classes/                 ← Classes app
/api/v1/uploads/                 ← Uploads app
/api/v1/files/                   ← Files (MinIO) app
/api/v1/sharing/                 ← Sharing app
/api/v1/friends/                 ← Friends app
/api/v1/notifications/           ← Notifications app
/api/v1/storage/                 ← Storage app
/api/v1/schedule/                ← Schedule (auth required)
/api/v1/public/schedule/         ← Schedule (public, no auth)

# Legacy shortcuts (deprecated)
/register/
/login/
```

### 5.4 Middleware & Settings

#### `RequestLoggingMiddleware`

Custom middleware in `kibegi_api/middleware.py` that:
- Logs every inbound HTTP request: method, path, IP, user agent, response status, duration
- Redacts sensitive fields: `password`, `otp`, `token`, `access`, `refresh`
- Writes to `logs/kibegi_api.log` (rotating, 5 MB max, 5 backups)
- On log rotation, the `MinIORotatingFileHandler` automatically uploads old log files to the MinIO `logs/` prefix

#### JWT Settings

```python
ACCESS_TOKEN_LIFETIME  = 1 hour
REFRESH_TOKEN_LIFETIME = 7 days
ROTATE_REFRESH_TOKENS  = True   # New refresh token on each use
BLACKLIST_AFTER_ROTATION = True # Old refresh tokens are blacklisted
```

#### CORS

Allowed origins: `kibegi.com`, `www.kibegi.com`, `localhost:5173`, `localhost:4173`, `localhost:3000`, `127.0.0.1:5173`

---

## 6. Database Schema

### 6.1 `authentication.User`

> Custom user model replacing Django's default `auth.User`.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL, AUTO | |
| `email` | EmailField(255) | UNIQUE, NOT NULL | Used as USERNAME_FIELD |
| `full_name` | CharField(255) | NOT NULL | |
| `user_type` | CharField(10) | NOT NULL, DEFAULT `student` | Choices: `student`, `lecturer` |
| `profile_image` | ImageField | NULL, BLANK | Path: `profiles/{id}/profile.{ext}` |
| `is_active` | BooleanField | DEFAULT True | |
| `is_staff` | BooleanField | DEFAULT False | |
| `date_joined` | DateTimeField | AUTO_NOW_ADD | |
| `password` | CharField | NOT NULL | Hashed (inherited) |
| `last_login` | DateTimeField | NULL | (inherited) |

---

### 6.2 `authentication.PasswordResetOTP`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL, AUTO | |
| `email` | EmailField | NOT NULL | Target email |
| `code` | CharField(32) | NOT NULL | 6-digit OTP (numeric) |
| `purpose` | CharField(32) | DEFAULT `password_reset` | `registration` or `password_reset` |
| `reset_token` | CharField(128) | NULL, BLANK | UUID issued after OTP verification |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `expires_at` | DateTimeField | NOT NULL | `created_at + OTP_EXPIRY_SECONDS (300s)` |
| `is_used` | BooleanField | DEFAULT False | Prevents replay attacks |

---

### 6.3 `classes.Class`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUIDField (PK) | NOT NULL | uuid4 |
| `name` | CharField(200) | NOT NULL | |
| `description` | TextField | BLANK | |
| `class_code` | CharField(6) | UNIQUE, NOT NULL, INDEX | Auto-generated 6-char code |
| `is_public` | BooleanField | DEFAULT False | |
| `is_verified` | BooleanField | DEFAULT False | True = created by lecturer |
| `creator_id` | FK → User | CASCADE, NOT NULL | |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `updated_at` | DateTimeField | AUTO_NOW | |

*M2M through `Membership`*: `members` ↔ `User`

---

### 6.4 `classes.Membership`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `user_id` | FK → User | CASCADE, NOT NULL | |
| `class_obj_id` | FK → Class | CASCADE, NOT NULL | |
| `role` | CharField(20) | NOT NULL | Choices: `lecturer`, `student` |
| `joined_at` | DateTimeField | AUTO_NOW_ADD | |

**Unique constraint:** (`user_id`, `class_obj_id`)

---

### 6.5 `uploads.Upload`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUIDField (PK) | NOT NULL | uuid4 |
| `file` | FileField | NOT NULL | Path: `uploads/{uploader_id}/{filename}` |
| `file_name` | CharField(255) | NOT NULL | Original filename |
| `file_type` | CharField(20) | NOT NULL | Auto-detected: `document`, `image`, `video`, `audio`, `archive`, `spreadsheet`, `presentation`, `other` |
| `file_size` | BigIntegerField | NOT NULL | Bytes |
| `file_code` | CharField(8) | UNIQUE, NOT NULL, INDEX | Auto-generated 8-char code |
| `uploader_id` | FK → User | CASCADE, NOT NULL | |
| `class_obj_id` | FK → Class | CASCADE, NOT NULL | Required; file belongs to a class |
| `is_deleted` | BooleanField | DEFAULT False | Soft-delete flag |
| `deleted_at` | DateTimeField | NULL, BLANK | Set on soft-delete |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `updated_at` | DateTimeField | AUTO_NOW | |

**Business rule:** Files in trash (`is_deleted=True`) are permanently deletable after 21 days.

---

### 6.6 `sharing.SharedFile`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUIDField (PK) | NOT NULL | uuid4 |
| `upload_id` | FK → Upload | CASCADE, NOT NULL | |
| `shared_by_id` | FK → User | CASCADE, NOT NULL | File owner / sharer |
| `shared_with_id` | FK → User | CASCADE, NOT NULL | Recipient |
| `status` | CharField(20) | DEFAULT `pending` | Choices: `pending`, `accepted`, `rejected` |
| `message` | TextField(500) | BLANK | Optional note from sharer |
| `shared_at` | DateTimeField | AUTO_NOW_ADD | |
| `accepted_at` | DateTimeField | NULL, BLANK | |
| `rejected_at` | DateTimeField | NULL, BLANK | |

**Unique constraint:** (`upload_id`, `shared_with_id`)  
**Indexes:** (`status`, `shared_at`), (`shared_with_id`, `status`)

---

### 6.7 `friends.Friendship`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `user_id` | FK → User | CASCADE, NOT NULL | Request sender |
| `friend_id` | FK → User | CASCADE, NOT NULL | Request receiver |
| `nickname` | CharField(100) | BLANK | Custom alias for friend |
| `status` | CharField(20) | DEFAULT `pending`, INDEX | Choices: `pending`, `accepted` |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `accepted_at` | DateTimeField | NULL, BLANK | |

**Unique constraint:** (`user_id`, `friend_id`)  
**Indexes:** (`user_id`, `status`), (`friend_id`, `status`)

---

### 6.8 `notifications.Notification`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `user_id` | FK → User | CASCADE, NOT NULL | Recipient |
| `notification_type` | CharField(30) | NOT NULL | See type choices below |
| `content` | TextField | NOT NULL | Human-readable message |
| `related_object_id` | CharField(100) | BLANK | ID of related object (share ID, friendship ID) |
| `is_read` | BooleanField | DEFAULT False | |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |

**Notification Types:** `share_request`, `share_accepted`, `share_rejected`, `friend_request`, `friend_accepted`, `upload_created`, `class_joined`, `file_shared` (legacy)

**Indexes:** (`user_id`, `is_read`), (`user_id`, `-created_at`)

---

### 6.9 `schedule.ScheduleCalendar`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `owner_id` | FK → User | CASCADE, NOT NULL | |
| `name` | CharField(255) | NOT NULL | Display name |
| `calendar_type` | CharField(20) | NOT NULL | Choices: `classes`, `examination` |
| `description` | TextField | NULL, BLANK | |
| `is_public_sync` | BooleanField | DEFAULT True | Enables public token URLs |
| `share_token` | CharField(255) | UNIQUE, NOT NULL | Stable high-entropy token |
| `calendar_code` | CharField(6) | UNIQUE, NOT NULL | Short human-readable code |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `updated_at` | DateTimeField | AUTO_NOW | |

**Unique constraint:** (`owner_id`, `calendar_type`) — one calendar per type per user

---

### 6.10 `schedule.ScheduleEvent`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `calendar_id` | FK → ScheduleCalendar | CASCADE, NOT NULL | |
| `title` | CharField(255) | NOT NULL | |
| `description` | TextField | NULL, BLANK | |
| `location` | CharField(255) | NULL, BLANK | |
| `start_at` | DateTimeField | NOT NULL | |
| `end_at` | DateTimeField | NOT NULL | Must be > `start_at` |
| `event_type` | CharField(20) | DEFAULT `other` | Choices: `class`, `exam`, `study`, `deadline`, `meeting`, `other` |
| `recurrence` | CharField(20) | DEFAULT `none` | Choices: `none`, `daily`, `weekly`, `monthly` |
| `days` | JSONField | NULL, BLANK | List of weekdays for weekly recurrence |
| `reminder_minutes` | PositiveIntegerField | DEFAULT 15 | |
| `source` | CharField(20) | DEFAULT `manual` | Choices: `manual`, `import`, `system` |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `updated_at` | DateTimeField | AUTO_NOW | |

**Indexes:** (`calendar_id`, `start_at`), (`calendar_id`, `event_type`)

---

### 6.11 `schedule.ScheduleSyncAccessLog`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField (PK) | |
| `calendar_id` | FK → ScheduleCalendar | CASCADE |
| `access_type` | CharField(20) | Values: `subscribe`, `download`, `info`, `qr` |
| `ip_address` | GenericIPAddressField | NULL |
| `user_agent` | TextField | BLANK |
| `accessed_at` | DateTimeField | AUTO_NOW_ADD |

---

### 6.12 `storage.UserStorage`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | BigAutoField (PK) | NOT NULL | |
| `user_id` | OneToOneField → User | CASCADE, NOT NULL | One record per user |
| `total_quota_mb` | DecimalField(10,2) | DEFAULT 50.00, ≥0 | Configurable quota in MB |
| `used_storage_bytes` | BigIntegerField | DEFAULT 0, ≥0 | Updated on upload/delete |
| `created_at` | DateTimeField | AUTO_NOW_ADD | |
| `updated_at` | DateTimeField | AUTO_NOW | |
| `last_calculated` | DateTimeField | AUTO_NOW | |

**Computed properties:** `used_storage_mb`, `free_storage_mb`, `free_storage_bytes`, `usage_percentage`, `is_full`

---

### 6.13 `storage.StorageUsageHistory`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField (PK) | |
| `user_storage_id` | FK → UserStorage | CASCADE |
| `used_storage_bytes` | BigIntegerField | Snapshot at record time |
| `recorded_at` | DateTimeField | AUTO_NOW_ADD |

**Index:** (`user_storage_id`, `-recorded_at`)

---

### 6.14 Entity-Relationship Overview

```
User ──────────────────────────────────────────────────────────────
 │                                                                 │
 │ creates/joins                                         has one  │
 ▼                                                                 ▼
Class ◄── Membership ──► User                           UserStorage
 │                                                           │
 │ has many                                        history records
 ▼                                                           ▼
Upload ◄───────── SharedFile ──────────────► User    StorageUsageHistory
 │ (uploader)      (shared_by / shared_with)
 │
 ▼
[MinIO/S3 file object]

User ◄───── Friendship ─────► User

User ◄───── Notification

User ──► ScheduleCalendar ──► ScheduleEvent
                │
                └──► ScheduleSyncAccessLog
```

---

## 7. API Endpoints Reference

> Base URL: `https://api.kibegi.com/api/v1/`  
> All authenticated endpoints require: `Authorization: Bearer <access_token>`

### 7.1 Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register/` | ❌ | Register; sends OTP email |
| POST | `/auth/register/verify/` | ❌ | Verify registration OTP → returns `access` + `refresh` |
| POST | `/auth/register/resend/` | ❌ | Resend OTP (rate-limited: 5/25min) |
| POST | `/auth/login/` | ❌ | Login → returns `access` + `refresh` |
| POST | `/auth/logout/` | ✅ | Blacklist refresh token |
| POST | `/auth/token/refresh/` | ❌ | Exchange refresh → new access token |
| POST | `/auth/password-reset/` | ❌ | Request password reset OTP |
| POST | `/auth/password-reset/verify/` | ❌ | Verify reset OTP → returns `reset_token` |
| POST | `/auth/password-reset/resend/` | ❌ | Resend reset OTP |
| POST | `/auth/password-reset-confirm/` | ❌ | Set new password using `reset_token` |
| POST | `/auth/change-password/` | ✅ | Change password (must know current) |
| GET | `/auth/profile/` | ✅ | Get current user profile |
| PUT/PATCH | `/auth/profile/` | ✅ | Update profile (full_name, profile_image) |

**Register Request:**
```json
{
  "email": "alice@example.com",
  "full_name": "Alice Smith",
  "password": "securepassword",
  "user_type": "student"
}
```

**Login Response:**
```json
{
  "access": "eyJhbG...",
  "refresh": "eyJhbG...",
  "user": { "id": 1, "email": "...", "full_name": "...", "user_type": "student" }
}
```

---

### 7.2 Classes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/classes/` | ✅ | List user's classes (created + joined) |
| POST | `/classes/` | ✅ | Create a new class |
| GET | `/classes/{id}/` | ✅ | Get class details |
| PUT/PATCH | `/classes/{id}/` | ✅ | Update class (creator only) |
| DELETE | `/classes/{id}/` | ✅ | Delete class (creator only) |
| POST | `/classes/join/` | ✅ | Join class by `class_code` |
| POST | `/classes/{id}/leave/` | ✅ | Leave class (non-creator only) |
| GET | `/classes/{id}/members/` | ✅ | List class members |

---

### 7.3 Uploads

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/uploads/` | ✅ | List uploads (filter by class, type, search) |
| POST | `/uploads/` | ✅ | Upload a file (multipart/form-data) |
| GET | `/uploads/{id}/` | ✅ | Get upload details |
| DELETE | `/uploads/{id}/` | ✅ | Soft-delete upload (move to trash) |
| GET | `/uploads/trash/` | ✅ | List trashed uploads |
| POST | `/uploads/{id}/restore/` | ✅ | Restore from trash |
| DELETE | `/uploads/{id}/permanent/` | ✅ | Permanently delete from trash |
| GET | `/uploads/search/?q=` | ✅ | Search uploads by filename |

**Upload Request (multipart):**
```
file        : <binary>
class_obj   : <class UUID>
```

---

### 7.4 Files (MinIO/S3)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/files/{id}/download/` | ✅ | Download file (streams from MinIO) |
| GET | `/files/{id}/preview/` | ✅ | Preview file inline (browser) |
| GET | `/files/{id}/metadata/` | ✅ | File metadata (name, size, type, URL) |

---

### 7.5 Sharing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sharing/` | ✅ | List all shares (sent + received) |
| POST | `/sharing/` | ✅ | Share a file with another user |
| GET | `/sharing/{id}/` | ✅ | Get share details |
| POST | `/sharing/{id}/accept/` | ✅ | Accept a received share |
| POST | `/sharing/{id}/reject/` | ✅ | Reject a received share |
| DELETE | `/sharing/{id}/` | ✅ | Cancel/remove a share |
| GET | `/sharing/received/` | ✅ | List files shared with me |
| GET | `/sharing/sent/` | ✅ | List files I've shared |

**Share Request:**
```json
{
  "upload": "<upload UUID>",
  "shared_with": "<user ID>",
  "message": "Here's the lecture notes!"
}
```

---

### 7.6 Friends

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/friends/` | ✅ | List all friends (accepted) |
| POST | `/friends/` | ✅ | Send friend request |
| GET | `/friends/pending/` | ✅ | List pending incoming requests |
| GET | `/friends/sent/` | ✅ | List sent pending requests |
| POST | `/friends/{id}/accept/` | ✅ | Accept friend request |
| DELETE | `/friends/{id}/` | ✅ | Remove friend or cancel request |
| GET | `/friends/search/?q=` | ✅ | Search users by name/email |
| PATCH | `/friends/{id}/nickname/` | ✅ | Set custom nickname |

---

### 7.7 Notifications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications/` | ✅ | List all notifications (paginated) |
| POST | `/notifications/{id}/read/` | ✅ | Mark one notification as read |
| POST | `/notifications/read-all/` | ✅ | Mark all notifications as read |
| GET | `/notifications/unread-count/` | ✅ | Get count of unread notifications |

---

### 7.8 Storage

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/storage/` | ✅ | Get storage usage stats |
| GET | `/storage/history/` | ✅ | Get storage usage history |

**Response:**
```json
{
  "total_quota_mb": 50.0,
  "used_storage_mb": 12.5,
  "free_storage_mb": 37.5,
  "used_storage_bytes": 13107200,
  "usage_percentage": 25.0,
  "is_full": false
}
```

---

### 7.9 Schedule

#### Authenticated Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/schedule/calendars/` | ✅ | List user's calendars |
| POST | `/schedule/calendars/` | ✅ | Create a calendar |
| GET | `/schedule/calendars/{id}/` | ✅ | Get calendar detail |
| PATCH | `/schedule/calendars/{id}/` | ✅ | Update calendar |
| DELETE | `/schedule/calendars/{id}/` | ✅ | Delete calendar |
| GET | `/schedule/calendars/{id}/events/` | ✅ | List events in calendar |
| POST | `/schedule/calendars/{id}/events/` | ✅ | Create event |
| GET | `/schedule/events/{id}/` | ✅ | Get event detail |
| PATCH | `/schedule/events/{id}/` | ✅ | Update event |
| DELETE | `/schedule/events/{id}/` | ✅ | Delete event |
| GET | `/schedule/calendars/{id}/qr/` | ✅ | Get QR code image for calendar |

#### Public Endpoints (No Auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/public/schedule/{token}/subscribe` | iCal feed (for Google Calendar etc.) |
| GET | `/public/schedule/{token}/download` | Download ICS file |
| GET | `/public/schedule/{token}/info` | Calendar metadata |
| GET | `/public/schedule/code/{code}/` | Lookup calendar by short code |

---

### 7.10 Core / Search

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/search/?q=` | ✅ | Global search across uploads, classes, users |
| GET | `/health/` | ❌ | Health check endpoint |

---

## 8. Data Flow Diagrams

### 8.1 User Registration & OTP Verification

```
User                   Frontend              Backend API            Email (SMTP)
 │                         │                      │                      │
 │── POST /auth/register/──►│                      │                      │
 │                         │── POST /auth/register/►                     │
 │                         │                      │── Create User ──────►DB
 │                         │                      │── Create OTP ───────►DB
 │                         │                      │── Send OTP email ───►│
 │                         │◄── 201 {message} ────│                      │
 │◄── "Check your email" ──│                      │                      │
 │                         │                      │◄── OTP delivered ────│
 │── Enter OTP ───────────►│                      │
 │                         │── POST /auth/register/verify/ {code} ──────►│
 │                         │                      │── Validate OTP ─────►DB
 │                         │                      │── Mark OTP used ────►DB
 │                         │                      │── Generate JWT ─────►│
 │                         │◄── 200 {access, refresh, user} ─────────────│
 │◄── Logged in! ──────────│
```

### 8.2 File Upload Flow

```
User              Frontend            Backend API           MinIO/S3           DB
 │                   │                    │                    │               │
 │── Select file ───►│                    │                    │               │
 │                   │──POST /uploads/ ──►│                    │               │
 │                   │  (multipart)       │── Check quota ────────────────────►│
 │                   │                   │◄── Quota OK ─────────────────────── │
 │                   │                   │── Upload file ────►│               │
 │                   │                   │◄── Storage URL ────│               │
 │                   │                   │── Create Upload ──────────────────►│
 │                   │                   │── Update UserStorage ─────────────►│
 │                   │◄── 201 {upload} ──│                    │               │
 │◄── Upload complete│                   │                    │               │
```

### 8.3 File Sharing Flow

```
Alice               Backend API              DB              Bob's Notifications
 │                      │                    │                        │
 │── POST /sharing/ ───►│                    │                        │
 │   {upload, shared_with: Bob}              │                        │
 │                      │── Create SharedFile (pending) ────────────►│DB
 │                      │── Create Notification for Bob ─────────────►│
 │◄── 201 {share} ──────│                    │                        │
 │                      │                    │                        │
 Bob                    │                    │                        │
 │── GET /notifications/►                   │                        │
 │◄── [{type: share_request, ...}] ─────────│                        │
 │── POST /sharing/{id}/accept/ ───────────►│                        │
 │                      │── Update status = 'accepted' ─────────────►│DB
 │                      │── Create Notification for Alice ───────────►│
 │◄── 200 {share} ──────│                    │                        │
```

### 8.4 Friend Request Flow

```
Alice              Backend API              DB             Bob
 │── POST /friends/ {friend: Bob} ─────────►│               │
 │                  │── Create Friendship (pending) ───────►│DB
 │                  │── Create Notification for Bob ────────►│
 │◄── 201 ──────────│                       │               │
 │                  │                       │               │
 Bob                │                                       │
 │── GET /friends/pending/ ─────────────────►              │
 │◄── [{user: Alice, ...}] ──────────────────              │
 │── POST /friends/{id}/accept/ ────────────►              │
 │                  │── Update status = accepted ──────────►│DB
 │                  │── Create Notification for Alice ──────►│
 │◄── 200 ──────────│                                       │
```

### 8.5 Schedule Sync Flow

```
User              Frontend           Backend API          Calendar App (Google)
 │── Add event ──►│                     │                       │
 │                │── POST /schedule/calendars/{id}/events/ ──►│
 │                │◄── 201 {event} ─────│                       │
 │                │                     │                       │
 │── Share calendar ──► copy token/code │                       │
 │                                      │                       │
 │                                      │◄── GET /public/schedule/{token}/subscribe
 │                                      │── Render ICS feed ───►│
 │                                      │── Log access ─────────►DB
 │                                      │                       │
 │                                      │    (auto-sync every ~15 min)
```

---

## 9. Frontend — React App Deep-Dive

### 9.1 Project Structure

```
kibegi-your-digital-school-bag/
├── src/
│   ├── main.tsx              ← React entry point
│   ├── App.tsx               ← Root router + providers
│   ├── index.css             ← Global styles + Tailwind directives
│   ├── vite-env.d.ts
│   │
│   ├── pages/                ← Page-level components (one dir per route)
│   │   ├── Index/            ← Landing page
│   │   ├── Login/
│   │   ├── Signup/
│   │   ├── ForgotPassword/
│   │   ├── PasswordResetRequest/
│   │   ├── PasswordResetVerify/
│   │   ├── PasswordResetConfirm/
│   │   ├── Dashboard/        ← Main dashboard (summary cards)
│   │   ├── Upload/           ← File upload form
│   │   ├── Files/            ← My files list
│   │   ├── Classes/          ← Classes list + create/join
│   │   ├── ClassDetails/     ← Class detail + members + files
│   │   ├── Schedule/         ← Calendar view + event CRUD
│   │   ├── Sharing/          ← Sent/received shares
│   │   ├── Friends/          ← Friend list + requests
│   │   ├── Notifications/    ← Notification inbox
│   │   ├── Storage/          ← Storage usage bar + history
│   │   ├── Trash/            ← Soft-deleted files
│   │   ├── Profile/          ← View/edit profile + change password
│   │   ├── Settings/         ← App settings (theme, language)
│   │   ├── Library/          ← Browse class resources
│   │   ├── Marketplace/      ← Resource marketplace (stub)
│   │   ├── About/
│   │   ├── HowToUse/
│   │   ├── Privacy/
│   │   └── NotFound/
│   │
│   ├── components/
│   │   ├── ProtectedRoute.tsx      ← Auth guard wrapper
│   │   ├── NavigationIndicator.tsx ← Page-load indicator bar
│   │   ├── NavLink.tsx             ← Styled nav link
│   │   ├── FilePreview.tsx         ← In-browser file preview modal
│   │   ├── layout/                 ← Sidebar, Header, MainLayout
│   │   ├── dashboard/              ← Dashboard widget components
│   │   ├── library/                ← Library-specific components
│   │   └── ui/                     ← ShadCN/Radix UI components
│   │
│   ├── contexts/
│   │   ├── AuthContext.tsx         ← Auth state (user, tokens, login/logout)
│   │   ├── ThemeContext.tsx        ← Dark/light theme
│   │   └── LanguageContext.tsx     ← i18n language toggle
│   │
│   ├── hooks/
│   │   └── usePageTitle.ts         ← Dynamic document title per route
│   │
│   ├── services/                   ← Axios API client functions
│   │   ├── authService.ts          ← All auth API calls
│   │   ├── classService.ts         ← Classes API
│   │   ├── classmatesService.ts    ← Classmates listing
│   │   ├── uploadService.ts        ← Upload/trash API
│   │   ├── fileService.ts          ← File download/preview
│   │   ├── sharingService.ts       ← Sharing API
│   │   ├── friendService.ts        ← Friends API (simple)
│   │   ├── friendsService.ts       ← Friends API (full)
│   │   ├── notificationService.ts  ← Notifications API
│   │   ├── scheduleService.ts      ← Schedule/calendar API
│   │   ├── storageService.ts       ← Storage stats API
│   │   ├── searchService.ts        ← Global search API
│   │   └── libraryService.ts       ← Library API
│   │
│   ├── lib/
│   │   └── utils.ts                ← Tailwind class merging utility
│   │
│   └── assets/                     ← Static images/icons
│
├── public/                         ← Vite public dir (favicon, manifest)
├── index.html                      ← HTML entry point + PWA meta tags
├── vite.config.ts                  ← Vite + PWA config
├── tailwind.config.ts              ← Tailwind theme extension
├── components.json                 ← ShadCN config
├── tsconfig.json
├── netlify.toml                    ← Netlify SPA redirect rules
└── package.json
```

### 9.2 Routing Map

| Path | Component | Auth Required | Notes |
|------|-----------|---------------|-------|
| `/` | `Index` | ❌ | Landing / marketing page |
| `/login` | `Login` | ❌ | |
| `/signup` | `Signup` | ❌ | |
| `/forgot-password` | `ForgotPassword` | ❌ | |
| `/password-reset` | `PasswordResetRequest` | ❌ | |
| `/password-reset/verify` | `PasswordResetVerify` | ❌ | OTP entry |
| `/password-reset/confirm` | `PasswordResetConfirm` | ❌ | New password |
| `/about` | `About` | ❌ | |
| `/how-to-use` | `HowToUse` | ❌ | |
| `/privacy` | `Privacy` | ❌ | |
| `/contact` | `Contact` | ❌ | |
| `/dashboard` | `Dashboard` | ✅ | |
| `/upload` | `Upload` | ✅ | |
| `/classes` | `Classes` | ✅ | |
| `/classes/:id` | `ClassDetails` | ✅ | |
| `/schedule` | `Schedule` | ✅ | |
| `/schedule/calendar/:calendarId` | `Schedule` | ✅ | Specific calendar |
| `/schedule/subscribe/:token` | `SchedulePublicSubscriptionPage` | ❌ | Public iCal |
| `/schedule/code` | `ScheduleCodeEntryPage` | ❌ | Enter code to find calendar |
| `/schedule/code/:code` | `SchedulePublicSubscriptionPage` | ❌ | |
| `/files` | `Files` | ✅ | My uploaded files |
| `/friends` | `Friends` | ✅ | |
| `/profile` | `Profile` | ✅ | |
| `/profile/edit` | `ProfileEdit` | ✅ | |
| `/profile/change-password` | `ProfileChangePassword` | ✅ | |
| `/trash` | `Trash` | ✅ | Soft-deleted files |
| `/sharing` | `Sharing` | ✅ | Shared files inbox/sent |
| `/notifications` | `Notifications` | ✅ | |
| `/settings` | `Settings` | ✅ | |
| `/storage` | `Storage` | ✅ | Quota bar + history |
| `/marketplace` | `Marketplace` | ✅ | |
| `/library` | `Library` | ✅ | |
| `*` | `NotFound` | — | 404 catch-all |

### 9.3 Context Providers

#### `AuthContext`

```typescript
interface AuthContextType {
  user: User | null;         // Current user object
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login(credentials): Promise<void>;
  logout(): Promise<void>;
  updateUser(data): void;    // Update local user state
}
```

- Stores tokens in `localStorage` / `js-cookie`
- Auto-refreshes access token using the refresh token
- Wraps the entire app; child components consume via `useContext(AuthContext)`

#### `ThemeContext`

- Provides `theme` (`light` | `dark`) and `setTheme`
- Applies CSS class `dark` to `document.documentElement`
- Persists selection to `localStorage`

#### `LanguageContext`

- Provides `language` (`en` | `sw` — English / Swahili) and `setLanguage`
- Persists to `localStorage`

### 9.4 Service Layer

All services follow the same pattern: Axios instance with `Authorization: Bearer <token>` header injected from `AuthContext`.

| Service File | Key Functions |
|---|---|
| `authService.ts` | `register()`, `verifyOTP()`, `login()`, `logout()`, `refreshToken()`, `getProfile()`, `updateProfile()`, `updateProfilePicture()`, `changePassword()`, `requestPasswordReset()`, `verifyResetOTP()`, `confirmPasswordReset()` |
| `classService.ts` | `getClasses()`, `createClass()`, `getClass()`, `updateClass()`, `deleteClass()`, `joinClass()`, `leaveClass()`, `getClassMembers()` |
| `uploadService.ts` | `uploadFile()`, `getUploads()`, `getUpload()`, `deleteUpload()`, `getTrashedUploads()`, `restoreUpload()`, `permanentDeleteUpload()`, `searchUploads()` |
| `fileService.ts` | `downloadFile()`, `previewFile()`, `getFileMetadata()` |
| `sharingService.ts` | `shareFile()`, `getShares()`, `getReceivedShares()`, `getSentShares()`, `acceptShare()`, `rejectShare()`, `deleteShare()` |
| `friendsService.ts` | `getFriends()`, `sendFriendRequest()`, `getPendingRequests()`, `getSentRequests()`, `acceptFriendRequest()`, `removeFriend()`, `searchUsers()`, `setNickname()` |
| `notificationService.ts` | `getNotifications()`, `markAsRead()`, `markAllAsRead()`, `getUnreadCount()` |
| `scheduleService.ts` | `getCalendars()`, `createCalendar()`, `getCalendar()`, `updateCalendar()`, `deleteCalendar()`, `getEvents()`, `createEvent()`, `updateEvent()`, `deleteEvent()`, `getCalendarQR()` |
| `storageService.ts` | `getStorageStats()`, `getStorageHistory()` |
| `searchService.ts` | `globalSearch(query)` |

### 9.5 Component Architecture

```
App
├── QueryClientProvider (TanStack Query)
├── ThemeProvider
├── LanguageProvider
├── AuthProvider
│   └── TooltipProvider
│       └── Toaster / Sonner (notifications)
│           └── BrowserRouter
│               └── AppContent
│                   ├── NavigationIndicator
│                   └── Routes
│                       ├── Public pages (Index, Login, Signup...)
│                       └── ProtectedRoute wrapper
│                           ├── MainLayout
│                           │   ├── Sidebar (navigation links)
│                           │   ├── Header (user menu, notifications badge)
│                           │   └── <page content>
│                           └── Page components
│                               ├── Dashboard (summary cards + recent activity)
│                               ├── Files (grid/list view, search, filter)
│                               ├── Classes (cards, join modal)
│                               ├── Schedule (calendar grid + event form)
│                               ├── Sharing (tabs: received / sent)
│                               ├── Friends (tabs: friends / pending / search)
│                               ├── Notifications (list, mark read)
│                               ├── Storage (usage bar, quota details)
│                               ├── Trash (restore / permanent delete)
│                               └── Profile (view / edit / change-password)
```

---

## 10. Security Design

| Concern | Implementation |
|---------|---------------|
| **Authentication** | JWT — Bearer token, 1h access / 7d refresh |
| **Token Refresh** | `ROTATE_REFRESH_TOKENS = True`; old tokens blacklisted via `rest_framework_simplejwt.token_blacklist` |
| **OTP Security** | 6-digit numeric OTP, 5-minute expiry, single-use (`is_used=True`), rate-limited resend (5/25 min) |
| **Password Storage** | Django's default `PBKDF2PasswordHasher` (SHA256, 720k iterations) |
| **CORS** | Explicit whitelist; credentials disallowed (no cookie-based auth) |
| **Request Logging** | Sensitive fields (`password`, `otp`, `token`, `access`, `refresh`) are redacted before logging |
| **File Access Control** | Files accessed only via authenticated endpoints; MinIO URLs not publicly guessable |
| **Shared File Access** | `can_access_file` property: only accepted shares + non-deleted files |
| **Storage Quota** | Backend enforces 50 MB limit before accepting uploads |
| **Soft Delete** | 21-day grace period prevents irreversible data loss |
| **Admin** | Superuser access via `/admin/` with Django admin 2FA possible |
| **HTTPS** | Enforced in production via Nginx TLS termination |
| **Input Validation** | DRF serializers + Zod on frontend |

---

## 11. Storage & File Management

### Storage Backend

```
Production: MinIO (self-hosted S3-compatible)
  Endpoint:  storage.kibegi.com (configurable via MINIO_API_ENDPOINT)
  Bucket:    kibegi-uploads
  Auth:      Access Key + Secret Key (AWS SDK v4 signatures)
  ACL:       Private (no public ACL)
  Path style: Enabled (AWS_S3_ADDRESSING_STYLE = 'path')

Development: Django FileSystemStorage (local /media/ directory)
```

### File Path Structure in MinIO

```
kibegi-uploads/
├── uploads/
│   └── {user_id}/
│       └── {original_filename}      ← Upload.file
├── profiles/
│   └── {user_id}/
│       └── profile.{ext}            ← User.profile_image
└── logs/
    └── kibegi_api.log.{timestamp}   ← Rotated log files
```

### Storage Quota Flow

```
1. User uploads file
2. Backend receives multipart request
3. Retrieve UserStorage for uploader
4. Check: used_storage_bytes + file.size <= total_quota_bytes (50 MB)
5. If over limit → 413 Quota Exceeded
6. Else → upload to MinIO, create Upload record
7. Django signal (post_save on Upload) updates UserStorage.used_storage_bytes
8. Django signal (post_delete / restore) reverses storage update
```

### File Type Detection

The `Upload.detect_file_type()` method uses both file extension and MIME type:

| Category | Extensions |
|----------|------------|
| document | pdf, doc, docx, txt, rtf, odt |
| spreadsheet | xls, xlsx, csv, ods |
| presentation | ppt, pptx, odp, key |
| image | jpg, jpeg, png, gif, bmp, svg, webp, ico |
| video | mp4, avi, mov, wmv, flv, mkv, webm, m4v |
| audio | mp3, wav, ogg, flac, m4a, aac, wma |
| archive | zip, rar, tar, gz, 7z, bz2, xz |
| other | anything else |

---

## 12. Notifications System

### Automatic Notification Triggers

Notifications are created inside model methods (`SharedFile.accept()`, `Friendship.accept()`) and service layer functions. No Celery/background tasks required — they fire synchronously.

| Trigger | Type | Recipient |
|---------|------|----------|
| File shared with user | `share_request` | Recipient |
| Share accepted | `share_accepted` | Original sharer |
| Share rejected | `share_rejected` | Original sharer |
| Friend request sent | `friend_request` | Recipient |
| Friend request accepted | `friend_accepted` | Original sender |
| Upload created | `upload_created` | Uploader (optional) |
| User joins class | `class_joined` | Class creator (optional) |

### Frontend Polling

The frontend `notificationService.ts` periodically calls `GET /notifications/unread-count/` to update the notification badge in the header. Full notification list is fetched when the user opens the Notifications page.

---

## 13. Deployment Architecture

```
Internet
   │
   ▼
Nginx (TLS termination, reverse proxy)
   │
   ├──► kibegi.com ──────────► Netlify (React SPA static hosting)
   │
   └──► api.kibegi.com ──────► Gunicorn (Django WSGI)
            │                      │
            │                      ├──► PostgreSQL
            │                      │
            │                      └──► MinIO
            │                           (storage.kibegi.com)
            │
            └──► 194.163.153.255 (VPS)
```

### Netlify (Frontend)

- Built with `vite build` → `dist/`
- `netlify.toml` configures SPA redirects (`/* → /index.html`)
- PWA enabled: service worker + offline support

### Django (Backend)

- Served by Gunicorn, fronted by Nginx
- Static files collected to `staticfiles/` (`collectstatic`)
- Media served via MinIO in production
- Environment variables via `.env` (python-decouple)

---

## 14. Environment Variables Reference

### Backend (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *required* | Django secret key |
| `DEBUG` | `True` | Set `False` in production |
| `DB_ENGINE` | `django.db.backends.sqlite3` | Use `django.db.backends.postgresql` for prod |
| `DB_NAME` | `kibegi_db` | Database name |
| `DB_USER` | `kibegi_user` | DB username |
| `DB_PASSWORD` | `""` | DB password |
| `DB_HOST` | `localhost` | DB host |
| `DB_PORT` | `5432` | DB port |
| `EMAIL_BACKEND` | `console` | SMTP backend for OTP emails |
| `EMAIL_HOST` | `localhost` | SMTP host |
| `EMAIL_PORT` | `25` | SMTP port |
| `EMAIL_HOST_USER` | `""` | SMTP username |
| `EMAIL_HOST_PASSWORD` | `""` | SMTP password |
| `EMAIL_USE_TLS` | `False` | TLS for SMTP |
| `DEFAULT_FROM_EMAIL` | `webmaster@localhost` | From address |
| `OTP_EXPIRY_SECONDS` | `300` | OTP validity period |
| `OTP_LENGTH` | `6` | OTP digit count |
| `MINIO_ENABLED` | `True` | Enable MinIO storage |
| `MINIO_API_ENDPOINT` | `""` | MinIO server host |
| `MINIO_ACCESS_KEY` | `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | `MINIO_SECRET_KEY` | MinIO secret key |
| `MINIO_BUCKET` | `kibegi-uploads` | Bucket name |
| `MINIO_SECURE` | `True` | Use HTTPS for MinIO |
| `MINIO_PUBLIC_BASE_URL` | `""` | Public URL prefix for media |
| `ENABLE_MINIO_LOG_UPLOAD` | `True` | Upload rotated logs to MinIO |
| `REDIS_URL` | `""` | Redis for cache (falls back to in-memory) |
| `SCHEDULE_FRONTEND_URL` | `""` | Frontend URL for schedule subscription page |
| `AWS_QUERYSTRING_AUTH` | `False` | Signed URLs for MinIO |
| `AWS_QUERYSTRING_EXPIRE` | `3600` | Signed URL expiry (seconds) |

### Frontend (`.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API URL (e.g. `https://api.kibegi.com`) |
| `VITE_MINIO_PUBLIC_URL` | MinIO public URL for file previews |

---

*This document was auto-generated from live codebase analysis on 2026-05-26.*
