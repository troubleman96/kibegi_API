# Uploads App

Complete file management system with automatic type detection, class-based organization, and soft delete functionality.

## 📋 Table of Contents

- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [File Upload Flow](#file-upload-flow)
- [Testing Guide](#testing-guide)
- [File Types & Validation](#file-types--validation)

---

## Overview

The uploads app provides functionality for:
- File upload and storage
- Automatic file type detection
- Automatic file size extraction
- Class-based file organization
- File access control by class membership
- Soft delete with recovery
- Unique file codes for easy sharing

**Key Features:**
- **Auto-Detection:** File type and size detected automatically
- **Class-Required:** All files must belong to a class
- **Access Control:** Only class members can view files
- **File Codes:** 8-character unique codes for each file
- **Soft Delete:** Files recoverable for 21 days
- **Size Limit:** 100MB maximum file size

---

## Models

### Upload Model

Represents an uploaded file in the system.

**Fields:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | UUID | Unique identifier | Primary Key, Auto-generated |
| `file` | FileField | The uploaded file | Required, uploads to `uploads/{user_id}/` |
| `file_name` | CharField | Display name | Max 255 chars, Auto-detected |
| `file_type` | CharField | File category | Auto-detected, 8 choices |
| `file_size` | BigInteger | File size in bytes | Auto-detected from file |
| `file_code` | CharField | Unique 8-char code | Unique, Auto-generated, Indexed |
| `uploader` | ForeignKey | User who uploaded | CASCADE delete, Auto-set |
| `class_obj` | ForeignKey | Associated class | CASCADE delete, Required |
| `is_deleted` | Boolean | Soft delete flag | Default: False |
| `deleted_at` | DateTime | Deletion timestamp | Null if not deleted |
| `created_at` | DateTime | Upload timestamp | Auto-generated |
| `updated_at` | DateTime | Last update | Auto-updated |

**File Type Choices:**

| Value | Description | Extensions |
|-------|-------------|------------|
| `document` | Documents | pdf, doc, docx, txt, rtf, odt |
| `spreadsheet` | Spreadsheets | xls, xlsx, csv, ods |
| `presentation` | Presentations | ppt, pptx, odp, key |
| `image` | Images | jpg, jpeg, png, gif, bmp, svg, webp, ico |
| `video` | Videos | mp4, avi, mov, wmv, flv, mkv, webm, m4v |
| `audio` | Audio | mp3, wav, ogg, flac, m4a, aac, wma |
| `archive` | Compressed | zip, rar, tar, gz, 7z, bz2, xz |
| `other` | Other types | Any other extension |

**Auto-Detection Logic:**

The system automatically detects file type using:
1. File extension analysis
2. MIME type checking
3. Intelligent categorization

**Example:**
- `document.pdf` → `file_type = 'document'`
- `photo.jpg` → `file_type = 'image'`
- `lecture.mp4` → `file_type = 'video'`
- `data.xlsx` → `file_type = 'spreadsheet'`

**Model Methods:**

```python
def detect_file_type(self):
    """Automatically detect file type from extension and MIME type"""
    
def soft_delete(self):
    """Mark file as deleted without removing from storage"""
    
def restore(self):
    """Restore a soft-deleted file"""
    
def is_permanently_deletable(self):
    """Check if file can be permanently deleted (after 21 days)"""
```

**File Storage:**
- **Path Pattern:** `uploads/{user_id}/{filename}`
- **Example:** `uploads/abc-123-def/document.pdf`
- **Media Root:** Configured in `settings.MEDIA_ROOT`
- **Access URL:** `/media/uploads/{user_id}/{filename}`

---

## API Endpoints

Base URL: `/api/v1/uploads/`

All endpoints require authentication (JWT token).

### 1. List & Upload Files

**Endpoint:** `GET /api/v1/uploads/`

**Authentication:** Required

**Description:** List files accessible to the user based on class membership.

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 10, max: 100)
- `class_id` - Filter by specific class UUID

**Access Rules:**
- **Students:** See all files in classes they're members of
- **Lecturers:** See only their own uploads in their classes

**Success Response (200):**
```json
{
  "count": 45,
  "next": "http://localhost:8000/api/v1/uploads/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "file_name": "lecture-notes.pdf",
      "file_type": "document",
      "file_size": 2456789,
      "file_code": "PDF12345",
      "uploader_name": "John Lecturer",
      "class_name": "Python Programming",
      "created_at": "2025-11-23T10:00:00Z"
    },
    {
      "id": "uuid",
      "file_name": "diagram.png",
      "file_type": "image",
      "file_size": 345678,
      "file_code": "IMG67890",
      "uploader_name": "Jane Lecturer",
      "class_name": "Web Design",
      "created_at": "2025-11-23T09:30:00Z"
    }
  ]
}
```

**File Size Display:**
- Returned in bytes
- Convert to human-readable: 2456789 bytes = 2.34 MB

---

**Endpoint:** `POST /api/v1/uploads/`

**Authentication:** Required

**Description:** Upload a new file to a class.

**Request Format:** `multipart/form-data`

**Required Fields:**
- `file` - The actual file (File object)
- `class_obj` - UUID of the class (String)

**Optional Fields:**
- `file_name` - Custom display name (defaults to uploaded filename if not provided)

**Auto-Detected Fields:**
- `file_name` - Extracted from uploaded file if not provided
- `file_type` - Automatically detected from file extension and MIME type
- `file_size` - Automatically extracted from file
- `file_code` - Auto-generated unique 8-char code
- `uploader` - Current authenticated user

**Example Request (Form Data):**
```
file: [binary file data]
class_obj: "665f6af4-b52f-415f-ab30-6f0ba182db70"
file_name: "My Custom Name.pdf"  (optional - uses uploaded filename if omitted)
```

**Example Request (cURL):**
```bash
# Upload with auto-detected filename
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "class_obj=665f6af4-b52f-415f-ab30-6f0ba182db70"

# Upload with custom filename
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "class_obj=665f6af4-b52f-415f-ab30-6f0ba182db70" \
  -F "file_name=Custom Name.pdf"
```

**Success Response (201):**
```json
{
  "message": "File uploaded successfully",
  "data": {
    "id": "uuid",
    "file": "/media/uploads/user-id/document.pdf",
    "file_name": "document.pdf",
    "file_type": "document",
    "file_size": 2456789,
    "file_code": "DOC12345",
    "uploader": "uuid",
    "uploader_name": "John Lecturer",
    "class_obj": "uuid",
    "class_name": "Python Programming",
    "is_deleted": false,
    "created_at": "2025-11-23T10:00:00Z",
    "updated_at": "2025-11-23T10:00:00Z",
    "file_url": "http://localhost:8000/media/uploads/user-id/document.pdf"
  }
}
```

**Validation & Errors:**

| Error | Status | Cause |
|-------|--------|-------|
| File too large | 400 | File exceeds 100MB |
| File type not allowed | 400 | Extension not in allowed list |
| Class required | 400 | Missing class_obj field |
| Invalid class | 400 | Class doesn't exist or user not member |
| No file provided | 400 | Missing file in request |

**File Validation Rules:**
- **Maximum Size:** 100MB (104,857,600 bytes)
- **Allowed Extensions:** See [File Types](#file-types--validation)
- **Class Membership:** Must be member of target class
- **Authentication:** Must be logged in

---

### 2. Get File Details

**Endpoint:** `GET /api/v1/uploads/{file_code}/`

**Authentication:** Required

**Description:** Get detailed information about a specific file.

**Success Response (200):**
```json
{
  "message": "Upload retrieved successfully",
  "data": {
    "id": "uuid",
    "file": "/media/uploads/user-id/document.pdf",
    "file_name": "lecture-notes.pdf",
    "file_type": "document",
    "file_size": 2456789,
    "file_code": "DOC12345",
    "uploader": "uuid",
    "uploader_name": "John Lecturer",
    "class_obj": "uuid",
    "class_name": "Python Programming",
    "is_deleted": false,
    "deleted_at": null,
    "created_at": "2025-11-23T10:00:00Z",
    "updated_at": "2025-11-23T10:00:00Z",
    "file_url": "http://localhost:8000/media/uploads/user-id/document.pdf"
  }
}
```

**Error Responses:**
- `404` - File not found or deleted
- `403` - Not a member of file's class

**Access Control:**
- Must be member of the class the file belongs to
- Deleted files return 404

---

### 3. Update File Metadata

**Endpoint:** `PUT /api/v1/uploads/{file_code}/` or `PATCH /api/v1/uploads/{file_code}/`

**Authentication:** Required (Uploader only)

**Description:** Update file metadata. Only uploader can update.

**Updatable Fields:**
- `file_name` - Change display name
- `class_obj` - Move to different class (if member)

**Cannot Update:**
- `file` - Cannot replace file (delete and re-upload instead)
- `file_type` - Auto-detected, read-only
- `file_size` - Auto-detected, read-only
- `file_code` - Permanent, read-only

**Request Body (Partial Update):**
```json
{
  "file_name": "Updated Lecture Notes.pdf"
}
```

**Success Response (200):**
```json
{
  "message": "Upload updated successfully",
  "data": {
    "id": "uuid",
    "file_name": "Updated Lecture Notes.pdf",
    "file_type": "document",
    "file_size": 2456789,
    "file_code": "DOC12345"
  }
}
```

**Error Responses:**
- `403` - Not the uploader
- `404` - File not found

---

### 4. Delete File (Soft Delete)

**Endpoint:** `DELETE /api/v1/uploads/{file_code}/`

**Authentication:** Required (Uploader only)

**Description:** Soft delete a file. File retained for 21 days.

**Success Response (200):**
```json
{
  "message": "Upload deleted successfully"
}
```

**Error Responses:**
- `403` - Not the uploader
- `404` - File not found

**Soft Delete Behavior:**
- File marked as deleted (`is_deleted = True`)
- `deleted_at` timestamp recorded
- File hidden from lists
- Physical file remains in storage
- Recoverable for 21 days
- After 21 days: eligible for permanent deletion

---

### 5. Get Recent Uploads

**Endpoint:** `GET /api/v1/uploads/recent/`

**Authentication:** Required

**Description:** Get most recently uploaded files across all accessible classes.

**Query Parameters:**
- `page` - Page number
- `page_size` - Items per page (default: 12)

**Success Response (200):**
```json
{
  "count": 100,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "file_name": "newest-file.pdf",
      "file_type": "document",
      "file_size": 1234567,
      "file_code": "NEW12345",
      "uploader_name": "John Lecturer",
      "class_name": "Python 101",
      "created_at": "2025-11-23T12:00:00Z"
    }
  ]
}
```

**Ordering:** Most recent first (descending created_at)

---

### 6. Restore Deleted File

**Endpoint:** `POST /api/v1/uploads/{file_code}/restore/`

**Authentication:** Required (Uploader only)

**Description:** Restore a soft-deleted file within 21 days.

**Success Response (200):**
```json
{
  "message": "Upload restored successfully",
  "data": {
    "id": "uuid",
    "file_name": "restored-file.pdf",
    "file_code": "DOC12345",
    "is_deleted": false,
    "deleted_at": null
  }
}
```

**Error Responses:**
- `400` - File not deleted / Past 21 days
- `403` - Not the uploader
- `404` - File not found

---

### 6B. Permanently Delete File

**Endpoint:** `DELETE /api/v1/uploads/{file_id}/permanent-delete/`

**Authentication:** Required (Uploader only)

**Description:** Permanently delete a file from trash (hard delete). ⚠️ **WARNING: This action is irreversible!**

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_id` | UUID | File's UUID (not file_code) |

**Requirements:**
- File must be in trash (`is_deleted = True`)
- You must be the uploader (owner)
- This is a **hard delete** - cannot be undone

**What Happens:**
1. Physical file is deleted from storage
2. Database record is permanently removed
3. All associated data is lost forever

**Success Response (200):**
```json
{
  "success": true,
  "message": "'document.pdf' permanently deleted"
}
```

**Error Responses:**
- `403` - Not the uploader
- `404` - File not found in trash

**⚠️ Important Notes:**
- This endpoint requires the file's **UUID** (from database), not the `file_code`
- File must be soft-deleted first (in trash)
- Get the UUID from trash list: `GET /api/v1/uploads/trash/`
- Once deleted, the file cannot be recovered
- Use with caution!

**Recommended Workflow:**
1. Soft delete file: `DELETE /api/v1/uploads/{file_code}/` → File goes to trash
2. View trash: `GET /api/v1/uploads/trash/` → Get file UUID
3. Permanent delete: `DELETE /api/v1/uploads/{uuid}/permanent-delete/` → File gone forever

---

### 7. Download File

**Endpoint:** `GET /api/v1/uploads/{file_code}/download/`

**Authentication:** Required

**Description:** Download file with proper headers for cross-device compatibility (PC, mobile, tablet).

**Features:**
- ✅ Works seamlessly on all devices
- ✅ Automatic MIME type detection
- ✅ Downloads with original filename
- ✅ Supports large file streaming
- ✅ Secure access control (class member OR accepted share)
- ✅ Proper unicode filename handling
- ✅ Cache headers for performance

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_code` | string | 8-character unique file code |

**Access Control:**
- Must be a member of the file's class, OR
- Have an accepted share for the file

**Success Response (200):**

Returns the file as binary data with headers:
```
Content-Type: application/pdf (or appropriate MIME type)
Content-Disposition: attachment; filename="document.pdf"
Content-Length: 2456789
Cache-Control: private, max-age=3600
X-Content-Type-Options: nosniff
```

The browser will automatically download the file with the correct filename.

**Example Usage:**

**Browser (Direct Link):**
```html
<a href="http://localhost:8000/api/v1/uploads/DOC12345/download/" 
   download>
  Download File
</a>
```

**JavaScript (Fetch API):**
```javascript
async function downloadFile(fileCode, fileName) {
  const response = await fetch(
    `http://localhost:8000/api/v1/uploads/${fileCode}/download/`,
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
downloadFile('DOC12345', 'document.pdf');
```

**cURL:**
```bash
# Download with authentication
curl -X GET http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o downloaded-file.pdf

# Or let cURL detect filename from headers
curl -OJ http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Mobile App (React Native):**
```javascript
import RNFS from 'react-native-fs';

async function downloadFile(fileCode, fileName) {
  const downloadUrl = `http://localhost:8000/api/v1/uploads/${fileCode}/download/`;
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
    // Open file or show success message
  }
}
```

**Error Responses:**

- `403` - Not authorized (not a class member and no accepted share)
- `404` - File not found, deleted, or doesn't exist on server
- `500` - Error reading file from disk

**Cross-Device Benefits:**

1. **PC/Laptop**: Direct download to Downloads folder with correct filename
2. **Mobile Browser**: Downloads to device with save dialog
3. **Mobile App**: Stream large files efficiently without loading all into memory
4. **Tablet**: Works identically to mobile/PC

**Use Cases:**

- Download lecture materials on mobile while commuting
- Share file link that works on any device
- Stream large videos without browser timeout
- Download course materials offline for later viewing

---

### 8. Direct File Access (Media URL)

**Example:** `http://localhost:8000/media/uploads/user-id/document.pdf`

**Authentication:** Handled by Django's file serving

**Notes:**
- In development: Django serves files directly
- In production: Use nginx/Apache to serve media files
- Configure `MEDIA_URL` and `MEDIA_ROOT` in settings

**Download with Original Name:**

```javascript
// Frontend example
fetch(file_url, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(response => response.blob())
.then(blob => {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = file_name;
  a.click();
});
```

---

## File Upload Flow

### Complete Upload Process

```
1. User authenticates (JWT token)
   ↓
2. User is member of a class
   ↓
3. POST /uploads/ with file and class_obj
   ↓
4. System validates:
   - File size ≤ 100MB
   - File extension allowed
   - User is class member
   ↓
5. System auto-detects:
   - file_type (document/image/video/etc)
   - file_size (bytes)
   - file_name (if not provided)
   ↓
6. System generates:
   - Unique file_code (8 chars)
   - Storage path (uploads/{user_id}/{filename})
   ↓
7. File saved to disk
   ↓
8. Database record created
   ↓
9. Return file details with file_url
```

### Access Control Flow

```
User requests file
   ↓
Check authentication
   ↓
Check if file exists and not deleted
   ↓
Check if user is member of file's class
   ↓
Grant/Deny access
```

---

## Testing Guide

### Using Swagger UI (Recommended)

Access: `http://localhost:8000/api/docs/`

**Complete Test Flow:**

**Step 1: Setup**
1. Login as lecturer
2. Create a class, note the `class_id` (UUID)
3. Copy JWT access token
4. Authorize Swagger with token

**Step 2: Upload File**
1. Go to `POST /api/v1/uploads/`
2. Click "Try it out"
3. Click "Choose File" and select a file (e.g., PDF, image)
4. Enter `class_obj` UUID from your class
5. Click "Execute"
6. Copy `file_code` from response
7. Note the auto-detected `file_type` and `file_size`

**Step 3: List Uploads**
1. Go to `GET /api/v1/uploads/`
2. Optionally add `class_id` query parameter
3. See your uploaded file in the list
4. Check `file_type` is correctly detected

**Step 4: Get File Details**
1. Go to `GET /api/v1/uploads/{file_code}/`
2. Enter your `file_code`
3. See complete file information
4. Note the `file_code` for downloading

**Step 5: Download File (Cross-Device)**
1. Go to `GET /api/v1/uploads/{file_code}/download/`
2. Enter your `file_code`
3. Click "Execute"
4. File downloads automatically with correct filename
5. Test on mobile/tablet - works the same way!

**Step 6: Update Metadata**
1. Go to `PATCH /api/v1/uploads/{file_code}/`
2. Update `file_name`:
   ```json
   {
     "file_name": "Renamed Document.pdf"
   }
   ```
3. Verify name changed

**Step 7: Test Access Control**
1. Login as different student
2. Try to access file without joining class
3. Should get 403/404 error
4. Join the class
5. Now can access the file

**Step 8: Delete and Restore**
1. Go to `DELETE /api/v1/uploads/{file_code}/`
2. File soft-deleted
3. Try to GET - returns 404
4. Go to `POST /api/v1/uploads/{file_code}/restore/`
5. File restored and accessible again

---

### Using cURL

**1. Upload File:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "class_obj=YOUR_CLASS_UUID"
```

**2. List Files:**
```bash
curl -X GET "http://localhost:8000/api/v1/uploads/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**3. Filter by Class:**
```bash
curl -X GET "http://localhost:8000/api/v1/uploads/?class_id=YOUR_CLASS_UUID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**4. Get File Details:**
```bash
curl -X GET http://localhost:8000/api/v1/uploads/DOC12345/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**5. Download File (Recommended for cross-device):**
```bash
# Download with auto-detected filename
curl -OJ http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Or specify output filename
curl -o myfile.pdf http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**6. Update File Name:**
```bash
curl -X PATCH http://localhost:8000/api/v1/uploads/DOC12345/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "New Name.pdf"
  }'
```

**7. Download File (Cross-Device Compatible):**
```bash
# Download with auto-detected filename
curl -OJ http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Or specify output filename
curl -o myfile.pdf http://localhost:8000/api/v1/uploads/DOC12345/download/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**8. Delete File:**
```bash
curl -X DELETE http://localhost:8000/api/v1/uploads/DOC12345/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**8. Restore File:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/DOC12345/restore/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**9. Get Recent Uploads:**
```bash
curl -X GET "http://localhost:8000/api/v1/uploads/recent/?page_size=12" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Testing File Type Detection

Upload different file types and verify auto-detection:

**Documents:**
```bash
# Upload PDF
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@document.pdf" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "document"

# Upload Word doc
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@report.docx" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "document"
```

**Images:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@photo.jpg" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "image"
```

**Spreadsheets:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@data.xlsx" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "spreadsheet"
```

**Videos:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@lecture.mp4" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "video"
```

**Archives:**
```bash
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@files.zip" \
  -F "class_obj=CLASS_UUID"
# Expected: file_type = "archive"
```

---

## File Types & Validation

### Allowed File Types

**Documents (file_type = 'document'):**
- `.pdf` - PDF documents
- `.doc`, `.docx` - Microsoft Word
- `.txt` - Plain text
- `.rtf` - Rich Text Format
- `.odt` - OpenDocument Text

**Spreadsheets (file_type = 'spreadsheet'):**
- `.xls`, `.xlsx` - Microsoft Excel
- `.csv` - Comma-Separated Values
- `.ods` - OpenDocument Spreadsheet

**Presentations (file_type = 'presentation'):**
- `.ppt`, `.pptx` - Microsoft PowerPoint
- `.odp` - OpenDocument Presentation
- `.key` - Apple Keynote

**Images (file_type = 'image'):**
- `.jpg`, `.jpeg` - JPEG images
- `.png` - PNG images
- `.gif` - GIF images
- `.bmp` - Bitmap images
- `.svg` - Scalable Vector Graphics
- `.webp` - WebP images
- `.ico` - Icon files

**Videos (file_type = 'video'):**
- `.mp4` - MP4 video
- `.avi` - AVI video
- `.mov` - QuickTime video
- `.wmv` - Windows Media Video
- `.flv` - Flash Video
- `.mkv` - Matroska Video
- `.webm` - WebM video
- `.m4v` - M4V video

**Audio (file_type = 'audio'):**
- `.mp3` - MP3 audio
- `.wav` - WAV audio
- `.ogg` - Ogg Vorbis
- `.flac` - FLAC audio
- `.m4a` - M4A audio
- `.aac` - AAC audio
- `.wma` - Windows Media Audio

**Archives (file_type = 'archive'):**
- `.zip` - ZIP archive
- `.rar` - RAR archive
- `.tar` - TAR archive
- `.gz` - Gzip archive
- `.7z` - 7-Zip archive
- `.bz2` - Bzip2 archive
- `.xz` - XZ archive

### File Size Limits

- **Maximum:** 100 MB (104,857,600 bytes)
- **Recommended:** Keep files under 50 MB for faster uploads
- **Large Files:** Consider splitting or compressing

### Storage Configuration

**Django Settings:**
```python
# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB
```

**Production Recommendations:**
- Use cloud storage (AWS S3, Google Cloud Storage)
- Configure CDN for faster delivery
- Implement virus scanning
- Set up automatic backups

---

## Common Errors & Solutions

### "File too large (max 100MB)"
**Cause:** File exceeds maximum size limit  
**Solution:** Compress file or split into smaller parts

### "File type '.xyz' not allowed"
**Cause:** File extension not in allowed list  
**Solution:** Convert to supported format or check extension

### "Class object required"
**Cause:** Missing class_obj in upload request  
**Solution:** Include class UUID in form data

### "Invalid class"
**Cause:** Class doesn't exist or not a member  
**Solution:** Join class first or check class_id

### "You don't have permission to update this file"
**Cause:** Not the uploader of the file  
**Solution:** Only uploader can update/delete files

### "Not a member of this class"
**Cause:** Trying to access file in class you haven't joined  
**Solution:** Join class first using class code

### "Upload not found"
**Cause:** File deleted or invalid file_code  
**Solution:** Check if file exists or restore if deleted

---

## Security & Best Practices

### File Upload Security

1. **File Validation:**
   - Extension whitelist (not blacklist)
   - Size limits enforced
   - MIME type checking

2. **Storage Security:**
   - Files stored outside web root
   - Random filename generation prevented (uses original)
   - Path traversal attacks prevented

3. **Access Control:**
   - Authentication required
   - Class membership verified
   - Uploader-only modifications

4. **Malware Protection:**
   - Consider virus scanning (not implemented)
   - Sandbox suspicious files
   - Monitor upload patterns

### Best Practices

**For Users:**
- Name files descriptively
- Compress large files before upload
- Use appropriate file formats
- Delete unused files

**For Developers:**
- Implement virus scanning in production
- Set up CDN for file delivery
- Monitor storage usage
- Implement file retention policies
- Add thumbnail generation for images
- Add preview generation for documents

---

## File Structure

```
uploads/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py               # App configuration
├── models.py             # Upload model
├── serializers.py        # DRF serializers
├── services.py           # FileHandler service
├── views.py              # API view classes
├── urls.py               # URL routing
├── README.md             # This file
├── migrations/           # Database migrations
│   ├── __init__.py
│   ├── 0001_initial.py
│   ├── 0002_upload_file_type_alter_upload_class_obj.py
│   └── 0003_alter_upload_class_obj.py
└── tests/                # Unit tests (TODO)
    └── __init__.py
```

---

## Related Documentation

- [Authentication App README](../authentication/README.md)
- [Classes App README](../classes/README.md)
- [Main Project README](../README.md)
- [Django File Uploads](https://docs.djangoproject.com/en/stable/topics/http/file-uploads/)
