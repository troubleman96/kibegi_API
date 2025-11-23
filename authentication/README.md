# Authentication App

Complete JWT-based authentication system with email verification, password reset, and user profile management.

## 📋 Table of Contents

- [Overview](#overview)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Authentication Flow](#authentication-flow)
- [Testing Guide](#testing-guide)
- [Security Features](#security-features)

---

## Overview

The authentication app provides a secure, production-ready authentication system with:
- JWT token-based authentication
- Email verification with OTP
- Password reset functionality
- User profile management
- Bilingual support (English/Swahili)
- Rate limiting and security measures

**Supported User Types:**
- `student` - Students who join classes
- `lecturer` - Lecturers who create and manage classes

---

## Models

### User Model

Extended Django's AbstractUser with custom fields.

**Fields:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | UUID | Unique identifier | Primary Key, Auto-generated |
| `email` | EmailField | User's email address | Unique, Required |
| `full_name` | CharField | User's full name | Max 255 chars, Required |
| `user_type` | CharField | Type of user | Choices: 'student', 'lecturer' |
| `is_verified` | Boolean | Email verification status | Default: False |
| `created_at` | DateTime | Account creation timestamp | Auto-generated |
| `updated_at` | DateTime | Last update timestamp | Auto-updated |

**Important Notes:**
- Username field is removed (email is used for authentication)
- Email must be unique across the system
- Users cannot access most features until `is_verified = True`

**Model Methods:**
```python
def __str__(self):
    return f"{self.full_name} ({self.email})"
```

---

### OTP Model

One-Time Password for email verification and password reset.

**Fields:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | UUID | Unique identifier | Primary Key, Auto-generated |
| `user` | ForeignKey | Associated user | CASCADE delete, Required |
| `code` | CharField | 6-digit OTP code | Max 6 chars, Indexed |
| `purpose` | CharField | OTP purpose | Choices: 'registration', 'password_reset' |
| `is_used` | Boolean | Whether OTP has been used | Default: False |
| `created_at` | DateTime | OTP creation time | Auto-generated |
| `expires_at` | DateTime | OTP expiration time | Auto-calculated (5 mins) |

**OTP Settings:**
- **Length:** 6 digits
- **Validity:** 5 minutes
- **Single-use:** OTPs cannot be reused after verification

**Model Methods:**
```python
def is_valid(self):
    """Check if OTP is valid (not expired and not used)"""
    return not self.is_used and timezone.now() < self.expires_at

def mark_as_used(self):
    """Mark OTP as used"""
    self.is_used = True
    self.save()
```

---

## API Endpoints

Base URL: `/api/v1/auth/`

### 1. User Registration

**Endpoint:** `POST /api/v1/auth/register/`

**Description:** Register a new user account. Sends OTP to email for verification.

**Request Body:**
```json
{
  "email": "student@example.com",
  "full_name": "John Doe",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "user_type": "student"
}
```

**Validation Rules:**
- Email must be valid and unique
- Password minimum 8 characters
- Password and password_confirm must match
- user_type must be 'student' or 'lecturer'
- full_name required

**Success Response (201):**
```json
{
  "message": "Registration successful. Please check your email for OTP.",
  "data": {
    "id": "uuid",
    "email": "student@example.com",
    "full_name": "John Doe",
    "user_type": "student",
    "is_verified": false,
    "created_at": "2025-11-23T10:30:00Z"
  }
}
```

**Error Responses:**
- `400` - Validation errors (email exists, passwords don't match, etc.)
- `500` - Server error

---

### 2. Verify Registration OTP

**Endpoint:** `POST /api/v1/auth/register/verify/`

**Description:** Verify email with OTP code sent during registration.

**Request Body:**
```json
{
  "email": "student@example.com",
  "otp": "123456"
}
```

**Success Response (200):**
```json
{
  "message": "Account verified successfully",
  "data": {
    "user": {
      "id": "uuid",
      "email": "student@example.com",
      "full_name": "John Doe",
      "is_verified": true
    },
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token"
  }
}
```

**Error Responses:**
- `400` - Invalid or expired OTP
- `404` - User not found

**Notes:**
- OTP expires after 5 minutes
- OTP can only be used once
- Automatically logs in user after verification

---

### 3. Resend Registration OTP

**Endpoint:** `POST /api/v1/auth/register/resend-otp/`

**Description:** Resend verification OTP to email.

**Request Body:**
```json
{
  "email": "student@example.com"
}
```

**Success Response (200):**
```json
{
  "message": "OTP resent successfully. Please check your email."
}
```

**Error Responses:**
- `400` - Email already verified or invalid
- `404` - User not found

---

### 4. User Login

**Endpoint:** `POST /api/v1/auth/login/`

**Description:** Login with email and password to get JWT tokens.

**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "SecurePass123!"
}
```

**Success Response (200):**
```json
{
  "message": "Login successful",
  "data": {
    "user": {
      "id": "uuid",
      "email": "student@example.com",
      "full_name": "John Doe",
      "user_type": "student",
      "is_verified": true
    },
    "access": "jwt_access_token_here",
    "refresh": "jwt_refresh_token_here"
  }
}
```

**Error Responses:**
- `400` - Account not verified
- `401` - Invalid credentials

**Token Usage:**
- **Access Token:** Include in `Authorization: Bearer <access_token>` header
- **Refresh Token:** Use to get new access token when expired
- **Access Token Lifetime:** 1 hour
- **Refresh Token Lifetime:** 7 days

---

### 5. User Logout

**Endpoint:** `POST /api/v1/auth/logout/`

**Authentication:** Required (Bearer token)

**Description:** Logout user by blacklisting refresh token.

**Request Body:**
```json
{
  "refresh": "jwt_refresh_token_here"
}
```

**Success Response (200):**
```json
{
  "message": "Logout successful"
}
```

**Error Responses:**
- `400` - Invalid or missing refresh token
- `401` - Unauthenticated

---

### 6. Get User Profile

**Endpoint:** `GET /api/v1/auth/profile/`

**Authentication:** Required (Bearer token)

**Description:** Get current user's profile information.

**Success Response (200):**
```json
{
  "message": "Profile retrieved successfully",
  "data": {
    "id": "uuid",
    "email": "student@example.com",
    "full_name": "John Doe",
    "user_type": "student",
    "is_verified": true,
    "created_at": "2025-11-23T10:30:00Z",
    "updated_at": "2025-11-23T10:30:00Z"
  }
}
```

**Error Responses:**
- `401` - Unauthenticated

---

### 7. Update User Profile

**Endpoint:** `PUT /api/v1/auth/profile/` or `PATCH /api/v1/auth/profile/`

**Authentication:** Required (Bearer token)

**Description:** Update user profile information.

**Request Body (Partial Update):**
```json
{
  "full_name": "John Smith"
}
```

**Updatable Fields:**
- `full_name` - User's full name
- `email` - Email address (must be unique)

**Success Response (200):**
```json
{
  "message": "Profile updated successfully",
  "data": {
    "id": "uuid",
    "email": "student@example.com",
    "full_name": "John Smith",
    "user_type": "student",
    "is_verified": true
  }
}
```

**Error Responses:**
- `400` - Validation error (email already exists)
- `401` - Unauthenticated

---

### 8. Change Password

**Endpoint:** `POST /api/v1/auth/change-password/`

**Authentication:** Required (Bearer token)

**Description:** Change password for authenticated user.

**Request Body:**
```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass456!",
  "new_password_confirm": "NewPass456!"
}
```

**Validation Rules:**
- old_password must be correct
- new_password minimum 8 characters
- new_password and new_password_confirm must match

**Success Response (200):**
```json
{
  "message": "Password changed successfully"
}
```

**Error Responses:**
- `400` - Validation error (wrong old password, passwords don't match)
- `401` - Unauthenticated

---

### 9. Password Reset Request

**Endpoint:** `POST /api/v1/auth/password-reset/`

**Description:** Request password reset. Sends OTP to email.

**Request Body:**
```json
{
  "email": "student@example.com"
}
```

**Success Response (200):**
```json
{
  "message": "Password reset OTP sent to your email"
}
```

**Error Responses:**
- `404` - Email not found

**Notes:**
- OTP expires after 5 minutes
- Can request new OTP if expired

---

### 10. Verify Password Reset OTP

**Endpoint:** `POST /api/v1/auth/password-reset/verify/`

**Description:** Verify OTP for password reset (step 2 of 3).

**Request Body:**
```json
{
  "email": "student@example.com",
  "otp": "123456"
}
```

**Success Response (200):**
```json
{
  "message": "OTP verified successfully. Proceed to reset password.",
  "data": {
    "reset_token": "temporary_token_for_password_reset"
  }
}
```

**Error Responses:**
- `400` - Invalid or expired OTP
- `404` - Email not found

**Notes:**
- Save `reset_token` for next step
- Token is temporary and single-use

---

### 11. Confirm New Password

**Endpoint:** `POST /api/v1/auth/password-reset/confirm/`

**Description:** Set new password after OTP verification (step 3 of 3).

**Request Body:**
```json
{
  "email": "student@example.com",
  "otp": "123456",
  "new_password": "NewSecurePass789!",
  "new_password_confirm": "NewSecurePass789!"
}
```

**Success Response (200):**
```json
{
  "message": "Password reset successful. You can now login with your new password."
}
```

**Error Responses:**
- `400` - Validation error (OTP invalid, passwords don't match)
- `404` - Email not found

---

### 12. Resend Password Reset OTP

**Endpoint:** `POST /api/v1/auth/password-reset/resend-otp/`

**Description:** Resend password reset OTP if expired.

**Request Body:**
```json
{
  "email": "student@example.com"
}
```

**Success Response (200):**
```json
{
  "message": "OTP resent successfully. Please check your email."
}
```

**Error Responses:**
- `404` - Email not found

---

## Authentication Flow

### Registration Flow

```
1. POST /register/
   ↓
2. Receive OTP via email
   ↓
3. POST /register/verify/ with OTP
   ↓
4. Account verified + Auto login with JWT tokens
   ↓
5. Use access token in Authorization header
```

### Login Flow

```
1. POST /login/ with email & password
   ↓
2. Receive access & refresh tokens
   ↓
3. Store tokens securely
   ↓
4. Include access token in requests:
   Authorization: Bearer <access_token>
```

### Password Reset Flow

```
1. POST /password-reset/ with email
   ↓
2. Receive OTP via email
   ↓
3. POST /password-reset/verify/ with OTP
   ↓
4. POST /password-reset/confirm/ with new password
   ↓
5. Login with new password
```

### Token Refresh Flow

```
1. Access token expires (401 error)
   ↓
2. POST to token refresh endpoint with refresh token
   ↓
3. Receive new access token
   ↓
4. Retry original request with new token
```

---

## Testing Guide

### Using Swagger UI (Recommended)

Access interactive API documentation at: `http://localhost:8000/api/docs/`

**Steps:**

1. **Register a User:**
   - Click on `POST /api/v1/auth/register/`
   - Click "Try it out"
   - Enter test data:
     ```json
     {
       "email": "test@example.com",
       "full_name": "Test User",
       "password": "TestPass123!",
       "password_confirm": "TestPass123!",
       "user_type": "student"
     }
     ```
   - Click "Execute"
   - Check your email for OTP (or check logs in development)

2. **Verify Registration:**
   - Click on `POST /api/v1/auth/register/verify/`
   - Enter email and OTP from email
   - Copy the `access` token from response

3. **Authorize Swagger:**
   - Click the "Authorize" button (🔓 icon) at top right
   - Enter: `Bearer <your_access_token>`
   - Click "Authorize"
   - Now all authenticated endpoints will work

4. **Test Protected Endpoints:**
   - Try `GET /api/v1/auth/profile/`
   - Try `POST /api/v1/auth/change-password/`
   - All requests now include your token automatically

### Using cURL

**1. Register User:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "full_name": "Test User",
    "password": "TestPass123!",
    "password_confirm": "TestPass123!",
    "user_type": "student"
  }'
```

**2. Verify Registration:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "otp": "123456"
  }'
```

**3. Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'
```

**4. Get Profile (Authenticated):**
```bash
curl -X GET http://localhost:8000/api/v1/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**5. Change Password:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/change-password/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "TestPass123!",
    "new_password": "NewPass456!",
    "new_password_confirm": "NewPass456!"
  }'
```

**6. Password Reset Flow:**

a. Request reset:
```bash
curl -X POST http://localhost:8000/api/v1/auth/password-reset/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'
```

b. Verify OTP:
```bash
curl -X POST http://localhost:8000/api/v1/auth/password-reset/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "otp": "123456"
  }'
```

c. Confirm new password:
```bash
curl -X POST http://localhost:8000/api/v1/auth/password-reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "otp": "123456",
    "new_password": "NewPass789!",
    "new_password_confirm": "NewPass789!"
  }'
```

### Testing OTP in Development

**Check Django Console Logs:**

When `EMAIL_BACKEND` is set to `console` in development, OTPs are printed to terminal:

```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Subject: Kibegi Digital School - Email Verification
From: noreply@kibegi.com
To: test@example.com

Your verification code is: 123456
This code will expire in 5 minutes.
```

**Check Email (Production):**

In production with real SMTP configured, OTPs are sent to actual email addresses.

---

## Security Features

### 1. JWT Token Security
- **Access Token Expiry:** 1 hour
- **Refresh Token Expiry:** 7 days
- **Token Blacklisting:** Logout invalidates refresh tokens
- **Bearer Authentication:** Tokens in Authorization header

### 2. Password Security
- **Minimum Length:** 8 characters
- **Django Password Validators:** Built-in validation rules
- **Hashing:** Django's PBKDF2 algorithm
- **No Plain Text Storage:** Passwords always hashed

### 3. OTP Security
- **Random Generation:** Cryptographically secure random 6-digit codes
- **Time-Limited:** 5-minute expiration
- **Single-Use:** Cannot reuse verified OTPs
- **Purpose-Specific:** Separate OTPs for registration and password reset

### 4. Email Verification
- **Required:** Users cannot access features until verified
- **Prevents Spam:** Fake emails cannot access system
- **Resend Option:** Can request new OTP if expired

### 5. Rate Limiting
- **Django Throttling:** Prevents brute force attacks
- **Per-User Limits:** Authenticated users have higher limits
- **Per-IP Limits:** Anonymous requests limited by IP

### 6. Input Validation
- **Email Format:** Django EmailField validation
- **Password Strength:** Django validators
- **SQL Injection:** Django ORM protects against SQL injection
- **XSS Protection:** DRF serializers escape output

### 7. CORS & CSRF
- **CORS Headers:** Configured for specific origins
- **CSRF Tokens:** DRF uses token authentication instead
- **Same-Site Cookies:** Secure cookie configuration

---

## Common Errors & Solutions

### "Account not verified"
**Cause:** Trying to login before verifying email  
**Solution:** Check email for OTP and verify at `/register/verify/`

### "Invalid or expired OTP"
**Cause:** OTP code is wrong or older than 5 minutes  
**Solution:** Request new OTP via `/register/resend-otp/` or `/password-reset/resend-otp/`

### "Email already exists"
**Cause:** Email is already registered  
**Solution:** Use different email or login with existing account

### "Invalid credentials"
**Cause:** Wrong email or password  
**Solution:** Double-check credentials or use password reset

### "Token has expired"
**Cause:** Access token older than 1 hour  
**Solution:** Use refresh token to get new access token

### "Authentication credentials were not provided"
**Cause:** Missing Authorization header  
**Solution:** Include `Authorization: Bearer <access_token>` header

---

## Environment Variables

Required environment variables in `.env`:

```env
# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com

# OTP Settings
OTP_LENGTH=6
OTP_EXPIRY_SECONDS=300

# JWT Settings (optional, has defaults)
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7
```

---

## File Structure

```
authentication/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py               # App configuration
├── models.py             # User and OTP models
├── serializers.py        # DRF serializers for validation
├── services.py           # Business logic (OTP, email)
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

- [Classes App README](../classes/README.md)
- [Uploads App README](../uploads/README.md)
- [Main Project README](../README.md)
- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [Simple JWT Docs](https://django-rest-framework-simplejwt.readthedocs.io/)
