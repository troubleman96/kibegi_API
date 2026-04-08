# Classes App

Complete class management system for digital school platform with membership roles, invitations, and class-based content organization.

## 📋 Table of Contents

- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Class Management Flow](#class-management-flow)
- [Testing Guide](#testing-guide)
- [Permissions & Roles](#permissions--roles)

---

## Overview

The classes app provides functionality for:
- Creating and managing classes (both lecturers and students)
- Verified classes (lecturer-created) vs. Study Groups (student-created)
- Class membership with roles (lecturer/student)
- Invitation system with unique codes
- Class-based access control
- Member management
- Soft delete functionality

**Anyone Can Create Classes:**
- **Lecturers:** Create **verified classes** (official courses) - automatically marked as verified
- **Students:** Create **study groups** (unofficial collaborative spaces) - marked as unverified
- Both types work identically, but verified classes are distinguished with a badge/indicator

**Class Types:**
- **Verified Classes (✓):** Created by lecturers, official courses, trusted content
- **Study Groups:** Created by students, peer learning, collaborative spaces

---

## Models

### Class Model

Represents a class/course in the digital school.

**Fields:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | UUID | Unique identifier | Primary Key, Auto-generated |
| `name` | CharField | Class name | Max 255 chars, Required |
| `description` | TextField | Class description | Optional |
| `class_code` | CharField | Unique 8-char invitation code | Unique, Auto-generated, Indexed |
| `is_verified` | Boolean | Official class badge | True for lecturer classes, False for student groups |
| `creator` | ForeignKey | User who created class | CASCADE delete, Required |
| `members` | ManyToMany | Class members | Through Membership model |
| `is_deleted` | Boolean | Soft delete flag | Default: False |
| `deleted_at` | DateTime | Deletion timestamp | Null if not deleted |
| `created_at` | DateTime | Creation timestamp | Auto-generated |
| `updated_at` | DateTime | Last update timestamp | Auto-updated |

**Important Notes:**
- `class_code` is automatically generated (8 characters, alphanumeric)
- **Anyone can create classes** (students and lecturers)
- `is_verified` is auto-set: `True` for lecturer classes, `False` for student study groups
- Creator is automatically added as member with appropriate role
- Lecturer creators get 'lecturer' role, student creators get 'student' role
- Soft delete keeps data for 21 days before permanent deletion

**Model Methods:**
```python
def soft_delete(self):
    """Mark class as deleted without removing from database"""
    
def restore(self):
    """Restore a soft-deleted class"""
    
def is_permanently_deletable(self):
    """Check if class can be permanently deleted (after 21 days)"""
```

**Computed Properties:**
- `member_count` - Total number of members (via annotation)
- `is_member` - Check if user is member (context-dependent)
- `user_role` - Get current user's role in class (context-dependent)

---

### Membership Model

Represents relationship between users and classes with roles.

**Fields:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | UUID | Unique identifier | Primary Key, Auto-generated |
| `user` | ForeignKey | Member user | CASCADE delete, Required |
| `class_obj` | ForeignKey | Associated class | CASCADE delete, Required |
| `role` | CharField | Member's role | Choices: 'lecturer', 'student' |
| `joined_at` | DateTime | Join timestamp | Auto-generated |

**Important Notes:**
- Unique constraint on (user, class_obj) - no duplicate memberships
- Creator is automatically added with 'lecturer' role
- Students join with invitation code
- Cascade delete when user or class is deleted

**Role Choices:**
- `lecturer` - Full management access
- `student` - View and participate access

---

## API Endpoints

Base URL: `/api/v1/classes/`

All endpoints require authentication (JWT token).

### 1. List & Create Classes

**Endpoint:** `GET /api/v1/classes/`

**Authentication:** Required

**Description:** List all classes accessible to the user.

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 10, max: 100)
- `search` - Search by class name or description

**Access Rules:**
- Lecturers see classes they created or are members of
- Students see classes they joined

**Success Response (200):**
```json
{
  "count": 15,
  "next": "http://localhost:8000/api/v1/classes/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Introduction to Python",
      "description": "Learn Python basics",
      "class_code": "ABC12345",
      "creator_name": "John Lecturer",
      "member_count": 25,
      "created_at": "2025-11-23T10:00:00Z"
    }
  ]
}
```

---

**Endpoint:** `POST /api/v1/classes/`

**Authentication:** Required (Any authenticated user)

**Description:** Create a new class. Anyone can create classes - lecturers create verified classes, students create study groups.

**Request Body:**
```json
{
  "name": "Advanced Django Development",
  "description": "Learn advanced Django patterns and best practices"
}
```

**Validation Rules:**
- `name` is required (max 255 characters)
- `description` is optional
- **Any authenticated user** can create classes
- Lecturers create **verified classes** (is_verified = true)
- Students create **study groups** (is_verified = false)

**Success Response (201):**
```json
{
  "message": "Class created successfully",
  "data": {
    "id": "uuid",
    "name": "Advanced Django Development",
    "description": "Learn advanced Django patterns and best practices",
    "class_code": "XYZ78901",
    "is_verified": true,
    "creator": "uuid",
    "creator_name": "John Lecturer",
    "creator_type": "lecturer",
    "member_count": 1,
    "is_member": true,
    "user_role": "lecturer",
    "is_deleted": false,
    "created_at": "2025-11-23T10:00:00Z",
    "updated_at": "2025-11-23T10:00:00Z"
  }
}
```

**Example: Student Creating Study Group:**
```json
{
  "message": "Class created successfully",
  "data": {
    "id": "uuid",
    "name": "Python Study Group",
    "description": "Let's learn Python together!",
    "class_code": "STU12345",
    "is_verified": false,
    "creator_name": "Jane Student",
    "creator_type": "student",
    "user_role": "student"
  }
}
```

**Error Responses:**
- `400` - Validation error (missing name, etc.)
- `401` - Not authenticated

**Automatic Actions:**
- Generates unique 8-character `class_code`
- Sets `is_verified` based on creator's `user_type`:
  - Lecturer → `is_verified = true` (Official Class ✓)
  - Student → `is_verified = false` (Study Group)
- Adds creator as member with role matching their user_type:
  - Lecturer → role = 'lecturer'
  - Student → role = 'student'
- Sets `created_at` and `updated_at` timestamps

---

### 2. Get Class Details

**Endpoint:** `GET /api/v1/classes/{id}/`

**Authentication:** Required

**Description:** Get detailed information about a specific class, including comprehensive upload statistics and recent files. This endpoint provides rich data for building class dashboard UIs that show upload activity and help students see which lecturers are actively sharing materials.

**Success Response (200):**
```json
{
  "message": "Class retrieved successfully",
  "data": {
    "id": "uuid",
    "name": "Advanced Django Development",
    "description": "Learn advanced Django patterns",
    "class_code": "XYZ78901",
    "is_public": false,
    "is_verified": true,
    "creator": "uuid",
    "creator_name": "John Lecturer",
    "creator_type": "lecturer",
    "member_count": 25,
    "is_member": true,
    "user_role": "student",
    "created_at": "2025-11-23T10:00:00Z",
    "updated_at": "2025-11-23T10:00:00Z",
    
    "uploads_summary": {
      "total_uploads": 15,
      "uploads_by_type": {
        "document": 8,
        "presentation": 4,
        "image": 2,
        "spreadsheet": 1
      },
      "total_size_bytes": 52428800,
      "total_size_mb": 50.0,
      "lecturers_with_uploads": 2,
      "active_contributors": 3
    },
    
    "recent_uploads": [
      {
        "id": "uuid",
        "file_name": "Week5_Lecture_Notes.pdf",
        "file_type": "document",
        "file_size": 2048576,
        "file_code": "ABC12345",
        "uploader_id": "uuid",
        "uploader_name": "John Lecturer",
        "uploader_type": "lecturer",
        "created_at": "2025-11-25T14:30:00Z"
      },
      {
        "id": "uuid",
        "file_name": "Assignment3_Solution.pptx",
        "file_type": "presentation",
        "file_size": 5242880,
        "file_code": "DEF67890",
        "uploader_id": "uuid",
        "uploader_name": "Jane Lecturer",
        "uploader_type": "lecturer",
        "created_at": "2025-11-24T10:15:00Z"
      }
    ],
    
    "uploader_stats": [
      {
        "uploader_id": "uuid",
        "uploader_name": "John Lecturer",
        "uploader_type": "lecturer",
        "upload_count": 8,
        "is_active_contributor": true
      },
      {
        "uploader_id": "uuid",
        "uploader_name": "Jane Lecturer",
        "uploader_type": "lecturer",
        "upload_count": 5,
        "is_active_contributor": true
      },
      {
        "uploader_id": "uuid",
        "uploader_name": "Student One",
        "uploader_type": "student",
        "upload_count": 2,
        "is_active_contributor": false
      }
    ]
  }
}
```

**Error Responses:**
- `403` - User doesn't have access to this class
- `404` - Class not found

**Response Fields:**

*Basic Class Info:*
- `is_verified` - True for official lecturer classes, False for student study groups
- `creator_type` - 'lecturer' or 'student' - who created the class
- `member_count` - Total members in class
- `is_member` - Whether current user is a member
- `user_role` - Current user's role ('lecturer' or 'student') or null

*Uploads Summary (`uploads_summary`):*
- `total_uploads` - Total number of non-deleted uploads in the class
- `uploads_by_type` - Dictionary of upload counts by file type (document, image, video, etc.)
- `total_size_bytes` - Total size of all uploads in bytes
- `total_size_mb` - Total size in megabytes (rounded to 2 decimal places)
- `lecturers_with_uploads` - Number of lecturers who have uploaded at least one file
- `active_contributors` - Number of members with more than 2 uploads

*Recent Uploads (`recent_uploads`):*
- Returns the 10 most recent non-deleted uploads
- Each upload includes: file info, uploader details, and upload timestamp
- Sorted by `created_at` descending (newest first)

*Uploader Statistics (`uploader_stats`):*
- List of all members who have uploaded files to this class
- Sorted by `upload_count` descending (most uploads first)
- `is_active_contributor` - True if the user has uploaded more than 2 files
- Useful for showing students which lecturers are actively sharing materials

**UI Usage Tips:**
1. Use `uploads_summary.lecturers_with_uploads` to show how many instructors are actively contributing
2. Use `uploader_stats` to display a leaderboard of contributors
3. Use `is_active_contributor` to highlight members who consistently share materials
4. Use `recent_uploads` to show a quick preview of latest class materials
5. Use `uploads_by_type` to show a breakdown chart of file types

---

### 3. Update Class

**Endpoint:** `PUT /api/v1/classes/{class_code}/` or `PATCH /api/v1/classes/{class_code}/`

**Authentication:** Required (Creator only)

**Description:** Update class information. Only the creator can update.

**Request Body (Partial Update):**
```json
{
  "name": "Advanced Django & DRF",
  "description": "Updated description"
}
```

**Updatable Fields:**
- `name` - Class name
- `description` - Class description

**Success Response (200):**
```json
{
  "message": "Class updated successfully",
  "data": {
    "id": "uuid",
    "name": "Advanced Django & DRF",
    "description": "Updated description",
    "class_code": "XYZ78901",
    "creator_name": "John Lecturer",
    "member_count": 25
  }
}
```

**Error Responses:**
- `403` - User is not the creator
- `404` - Class not found

---

### 4. Delete Class (Soft Delete)

**Endpoint:** `DELETE /api/v1/classes/{class_code}/`

**Authentication:** Required (Creator only)

**Description:** Soft delete a class. Data retained for 21 days.

**Success Response (200):**
```json
{
  "message": "Class deleted successfully"
}
```

**Error Responses:**
- `403` - User is not the creator
- `404` - Class not found

**Notes:**
- Soft delete: `is_deleted = True`, `deleted_at = now()`
- Class hidden from lists but data preserved
- Can be restored within 21 days
- After 21 days, eligible for permanent deletion

---

### 5. Join Class

**Endpoint:** `POST /api/v1/classes/join/`

**Authentication:** Required

**Description:** Join a class using invitation code.

**Request Body:**
```json
{
  "class_code": "XYZ78901"
}
```

**Success Response (200):**
```json
{
  "message": "Successfully joined the class",
  "data": {
    "id": "uuid",
    "name": "Advanced Django Development",
    "class_code": "XYZ78901",
    "creator_name": "John Lecturer",
    "member_count": 26,
    "is_member": true,
    "user_role": "student"
  }
}
```

**Error Responses:**
- `400` - Already a member of this class
- `404` - Invalid class code

**Automatic Actions:**
- Creates Membership with role='student'
- User immediately gains access to class content
- Member count increments

---

### 6. Leave Class

**Endpoint:** `POST /api/v1/classes/leave/`

**Authentication:** Required

**Description:** Leave a class you're a member of.

**Request Body:**
```json
{
  "class_code": "XYZ78901"
}
```

**Success Response (200):**
```json
{
  "message": "Successfully left the class"
}
```

**Error Responses:**
- `400` - Not a member / Cannot leave (creator)
- `403` - Creator cannot leave their own class
- `404` - Invalid class code

**Important Notes:**
- Class creator cannot leave (must delete class instead)
- Membership is permanently removed
- User loses access to class content immediately

---

### 7. List Class Members

**Endpoint:** `GET /api/v1/classes/{class_code}/members/`

**Authentication:** Required (Members only)

**Description:** Get list of all members in a class.

**Query Parameters:**
- `page` - Page number
- `page_size` - Items per page

**Success Response (200):**
```json
{
  "count": 25,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "full_name": "John Lecturer",
      "email": "john@example.com",
      "user_type": "lecturer",
      "role": "lecturer",
      "joined_at": "2025-11-23T10:00:00Z"
    },
    {
      "id": "uuid",
      "full_name": "Jane Student",
      "email": "jane@example.com",
      "user_type": "student",
      "role": "student",
      "joined_at": "2025-11-23T11:30:00Z"
    }
  ]
}
```

**Error Responses:**
- `403` - Not a member of this class
- `404` - Class not found

**Member Information:**
- `role` - Role in this class (lecturer/student)
- `user_type` - Overall user type in system
- `joined_at` - When they joined this class

---

### 8. Restore Deleted Class

**Endpoint:** `POST /api/v1/classes/{class_code}/restore/`

**Authentication:** Required (Creator only)

**Description:** Restore a soft-deleted class within 21 days.

**Success Response (200):**
```json
{
  "message": "Class restored successfully",
  "data": {
    "id": "uuid",
    "name": "Advanced Django Development",
    "class_code": "XYZ78901",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

**Error Responses:**
- `400` - Class not deleted / Past 21 days
- `403` - User is not the creator
- `404` - Class not found

---

## Class Management Flow

### Create Class (Anyone)

```
1. Any authenticated user can create a class
   ↓
2. POST /classes/ {name, description}
   ↓
3. System checks creator's user_type:
   - Lecturer → is_verified = true (Official Class ✓)
   - Student → is_verified = false (Study Group)
   ↓
4. System generates class_code
   ↓
5. Creator added as member with matching role:
   - Lecturer creator → role = 'lecturer'
   - Student creator → role = 'student'
   ↓
6. Share class_code with others
   ↓
7. Manage: PUT /classes/{code}/ to update
   or DELETE /classes/{code}/ to delete
```

**Benefits of This Approach:**
- **Students** can create study groups for peer learning
- **Lecturers** create official classes (verified badge shows trust)
- **Flexibility** - both work the same way, just different verification status
- **Simple** - no complex permissions, anyone can organize learning
- **Clear** - verified badge distinguishes official courses from study groups

### Join Class (Student)

```
1. Receive class_code from creator (lecturer or student)
   ↓
2. POST /classes/join/ {class_code}
   ↓
3. System creates membership with role='student'
   ↓
4. Access class content and materials
   ↓
5. See if class is verified (✓) or study group
   ↓
6. POST /classes/leave/ to leave class
```

### View Class Members

```
1. Be a member of the class
   ↓
2. GET /classes/{code}/members/
   ↓
3. View all lecturers and students
   ↓
4. See roles and join dates
```

---

## Testing Guide

### Using Swagger UI (Recommended)

Access: `http://localhost:8000/api/docs/`

**Complete Test Flow:**

**Step 1: Setup Authentication**
1. Register and verify two accounts (one lecturer, one student)
2. We'll test both creating verified classes and study groups

**Step 2: Create Verified Class (as Lecturer)**
1. Login as lecturer, copy access token
2. Click "Authorize" button, enter: `Bearer <token>`
3. Go to `POST /api/v1/classes/`
4. Click "Try it out"
5. Enter:
   ```json
   {
     "name": "Official Python Course",
     "description": "Official course taught by lecturer"
   }
   ```
6. Click "Execute"
7. Note: `is_verified: true` and `creator_type: "lecturer"`
8. Copy `class_code` from response

**Step 3: Create Study Group (as Student)**
1. Logout or authorize with student token
2. Go to `POST /api/v1/classes/`
3. Enter:
   ```json
   {
     "name": "Python Study Group",
     "description": "Students helping each other learn Python"
   }
   ```
4. Click "Execute"
5. Note: `is_verified: false` and `creator_type: "student"`
6. Copy this `class_code` too

**Step 4: Compare Both Classes**
1. Go to `GET /api/v1/classes/`
2. See both classes in your list
3. Verified class has `is_verified: true` ✓
4. Study group has `is_verified: false`
5. Both work identically for sharing and collaboration!

**Step 5: Join Either Class (as Another Student)**
1. Login as different student
2. Can join verified class OR study group
3. Go to `POST /api/v1/classes/join/`
4. Enter class_code of your choice
5. Successfully join either type!

**Step 6: View All Classes**
1. Go to `GET /api/v1/classes/`
2. Filter by verified: check `is_verified` field
3. See creator_type to know who made it

**Step 7: Test Class Details**
1. Go to `GET /api/v1/classes/{class_code}/`
2. Check `is_verified` field:
   - `true` = Official lecturer class ✓
   - `false` = Student study group
3. See `creator_type` and `creator_name`

**Step 6: View Members**
1. Go to `GET /api/v1/classes/{class_code}/members/`
2. See both lecturer and student in list
3. Check roles and joined_at timestamps

**Step 8: Update Class Metadata**
1. Authorize as class creator (lecturer or student)
2. Go to `PATCH /api/v1/classes/{class_code}/`
3. Update name or description
4. Note: `is_verified` cannot be changed (permanent)

**Step 9: Leave Class**
1. Authorize as member (not creator)
2. Go to `POST /api/v1/classes/leave/`
3. Enter class_code
4. Verify you're no longer a member

**Step 10: Delete Class**
1. Authorize as creator (works for both lecturers and students)
2. Go to `DELETE /api/v1/classes/{class_code}/`
3. Class is soft-deleted

**Step 11: Restore Class**
1. Go to `POST /api/v1/classes/{class_code}/restore/`
2. Class is restored

---

### Using cURL

**1. Create Verified Class (Lecturer):**
```bash
curl -X POST http://localhost:8000/api/v1/classes/ \
  -H "Authorization: Bearer LECTURER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Official Python Course",
    "description": "Learn Python - official course"
  }'
# Response includes: "is_verified": true
```

**2. Create Study Group (Student):**
```bash
curl -X POST http://localhost:8000/api/v1/classes/ \
  -H "Authorization: Bearer STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python Study Buddies",
    "description": "Study group for Python learners"
  }'
# Response includes: "is_verified": false
```

**2. List Classes:**
```bash
curl -X GET "http://localhost:8000/api/v1/classes/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
# Shows both verified classes and study groups with is_verified field
```

**3. Get Class Details:**
```bash
curl -X GET http://localhost:8000/api/v1/classes/ABC12345/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**4. Join Class (Student):**
```bash
curl -X POST http://localhost:8000/api/v1/classes/join/ \
  -H "Authorization: Bearer STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_code": "ABC12345"
  }'
```

**5. List Class Members:**
```bash
curl -X GET http://localhost:8000/api/v1/classes/ABC12345/members/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**6. Update Class (Lecturer):**
```bash
curl -X PATCH http://localhost:8000/api/v1/classes/ABC12345/ \
  -H "Authorization: Bearer LECTURER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Advanced Python Programming"
  }'
```

**7. Leave Class (Student):**
```bash
curl -X POST http://localhost:8000/api/v1/classes/leave/ \
  -H "Authorization: Bearer STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_code": "ABC12345"
  }'
```

**8. Delete Class (Soft Delete):**
```bash
curl -X DELETE http://localhost:8000/api/v1/classes/ABC12345/ \
  -H "Authorization: Bearer LECTURER_TOKEN"
```

**9. Restore Class:**
```bash
curl -X POST http://localhost:8000/api/v1/classes/ABC12345/restore/ \
  -H "Authorization: Bearer LECTURER_TOKEN"
```

---

## Permissions & Roles

### Class Creation
- **Who:** Any authenticated user (lecturers and students)
- **Lecturers Create:** Verified classes (is_verified = true) with 'lecturer' role
- **Students Create:** Study groups (is_verified = false) with 'student' role
- **Auto-Role:** Creator's role matches their user_type
- **Distinction:** Verified badge shows official lecturer classes

### Class Management
- **Who:** Class creator only (regardless of user_type)
- **Actions:** Update, delete, restore class
- **Limitation:** Cannot change is_verified status (permanent)
- **Transfer:** Cannot transfer ownership

### Joining Classes
- **Who:** Any authenticated user
- **Required:** Valid class_code
- **Role:** Always joins as 'student'
- **Both Types:** Can join verified classes or study groups equally
- **Restriction:** Cannot join if already member

### Leaving Classes
- **Who:** Class members (except creator)
- **Restriction:** Creator cannot leave own class
- **Action:** Permanently removes membership
- **Both Types:** Same process for verified and unverified classes

### Viewing Classes
- **Who:** Class members only
- **Lecturers see:** Own classes + classes joined as member
- **Students see:** Own study groups + classes they joined
- **Filter:** Can distinguish by is_verified field

### Viewing Members
- **Who:** Class members only
- **See:** All members with roles and join dates
- **Privacy:** Email and names visible to all members
- **Both Types:** Same visibility for verified and study groups

### Content Access
- **Who:** Class members only (any class type)
- **Uploads:** Files must be associated with class
- **Visibility:** Members see all class files
- **Verification:** No difference in access between verified/unverified classes

---

## Verified vs. Study Groups

### Visual Distinction

**Verified Classes (✓):**
- Created by lecturers
- `is_verified: true`
- `creator_type: "lecturer"`
- Display with verified badge/checkmark
- Indicates official, trusted course

**Study Groups:**
- Created by students
- `is_verified: false`
- `creator_type: "student"`
- Display without badge
- Indicates peer learning group

### Functional Similarity

Both class types have **identical functionality:**
- ✅ Generate unique class_code
- ✅ Invite members with code
- ✅ Upload and share files
- ✅ View member list
- ✅ Manage as creator
- ✅ Soft delete and restore
- ✅ Leave class (if not creator)

### Why This Design?

**Benefits:**
1. **Empowers Students:** Can organize their own learning
2. **Clear Trust Indicators:** Verified badge shows official content
3. **Flexibility:** Students collaborate without waiting for lecturers
4. **Simplicity:** Same code, same features, just different badge
5. **Scalability:** Peer learning grows organically

**Use Cases:**
- **Verified Classes:** CS101, Mathematics, Physics courses
- **Study Groups:** Exam prep groups, project teams, study circles

---

## Common Errors & Solutions

### "Only lecturers can create classes"
**Status:** This error is REMOVED - anyone can create classes now!
**New Behavior:** Students create study groups, lecturers create verified classes

### "Already a member of this class"
**Cause:** Trying to join class you're already in  
**Solution:** Check membership status first

### "Invalid class code"
**Cause:** Wrong or non-existent class_code  
**Solution:** Double-check code with class creator

### "Not a member of this class"
**Cause:** Trying to access content without membership  
**Solution:** Join class first with class_code

### "Only the creator can perform this action"
**Cause:** Non-creator trying to update/delete  
**Solution:** Only creator has management permissions

### "Creator cannot leave their own class"
**Cause:** Creator trying to use leave endpoint  
**Solution:** Delete class instead of leaving

### "Class not found"
**Cause:** Class deleted or invalid code  
**Solution:** Check if class exists or restore if deleted

---

## Database Queries & Performance

### Optimized Queries

**List Classes with Member Counts:**
```python
queryset = Class.objects.filter(is_deleted=False)\
    .annotate(total_members=Count('members'))\
    .select_related('creator')
```

**Check Membership:**
```python
is_member = class_obj.members.filter(id=user.id).exists()
```

**Get User Role:**
```python
membership = Membership.objects.filter(
    user=user,
    class_obj=class_obj
).first()
role = membership.role if membership else None
```

### Indexes

Optimized fields for fast lookups:
- `class_code` - Unique, indexed for invitation lookups
- `is_deleted` - Indexed for filtering active classes
- `(user, class_obj)` - Composite unique index in Membership

---

## File Structure

```
classes/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py               # App configuration
├── models.py             # Class and Membership models
├── serializers.py        # DRF serializers
├── views.py              # API view classes
├── urls.py               # URL routing
├── README.md             # This file
├── migrations/           # Database migrations
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/                # Unit tests (TODO)
    └── __init__.py
```

---

## Related Documentation

- [Authentication App README](../authentication/README.md)
- [Uploads App README](../uploads/README.md)
- [Main Project README](../README.md)
