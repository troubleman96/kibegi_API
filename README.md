# Kibegi Backend - Digital School API

Django REST API for Kibegi Digital School platform with JWT authentication, Swagger documentation, and bilingual support (English/Swahili).

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Add your email credentials and secrets

3. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

5. **Start server:**
   ```bash
   python manage.py runserver
   ```

6. **Access API Documentation:**
   - **Swagger UI:** http://localhost:8000/api/docs/
   - **ReDoc:** http://localhost:8000/api/redoc/
   - **OpenAPI Schema:** http://localhost:8000/api/schema/

## 📚 API Documentation

### Interactive API Testing
Visit **http://localhost:8000/api/docs/** for the Swagger UI interface where you can:
- View all available endpoints
- Test API requests directly from the browser
- Authenticate with JWT tokens
- See request/response schemas

### Authentication in Swagger
1. Login via `/api/v1/auth/login/` to get your access token
2. Click the **"Authorize"** button in Swagger UI
3. Enter your token (just the token, no "Bearer" prefix needed)
4. Now you can test all authenticated endpoints!

## Project Structure

```
Backend/
├── authentication/          # Auth app (IMPLEMENTED)
│   ├── models.py           # User, PasswordResetOTP models
│   ├── serializers.py      # Registration, Login, Profile serializers
│   ├── views.py            # Auth endpoints with Swagger docs
│   ├── urls.py
│   ├── services.py
│   ├── permissions.py
│   └── admin.py
│
├── classes/                 # Classes management (IMPLEMENTED)
│   ├── models.py           # Class, Membership models
│   ├── serializers.py      # Class, Join, Member serializers
│   ├── views.py            # Class CRUD, Join, Leave endpoints
│   ├── urls.py
│   ├── services.py         # ClassService for business logic
│   ├── permissions.py
│   └── admin.py
│
├── uploads/                 # File uploads & management (IMPLEMENTED)
│   ├── models.py           # Upload model with soft delete
│   ├── serializers.py      # Upload, UploadList serializers
│   ├── views.py            # Upload CRUD, Search, Trash endpoints
│   ├── urls.py
│   ├── services.py         # FileHandler for validation
│   └── admin.py
│
├── sharing/                 # File sharing system (SCAFFOLD)
├── friends/                 # Friends management (SCAFFOLD)
├── notifications/           # Notifications system (SCAFFOLD)
│
├── core/                    # Shared utilities
│   ├── utils/
│   │   ├── responses.py     # Standard API responses
│   │   ├── validators.py    # Shared validators
│   │   └── code_generator.py # Unique code generation
│   ├── permissions.py       # IsOwner, IsLecturer, IsStudent
│   └── pagination.py        # Standard pagination classes
│
├── kibegi_api/              # Project settings
│   ├── settings.py          # Django config + Swagger settings
│   ├── urls.py              # API routing + Swagger URLs
│   ├── middleware.py        # Request logging middleware
│   └── wsgi.py
│
├── media/                   # File uploads storage
├── logs/                    # Application logs
├── requirements.txt
├── .env
└── manage.py
```

## Project Structure

```
Backend/
├── authentication/          # Auth app (user management, JWT tokens, OTP)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   ├── permissions.py
│   └── admin.py
│
├── classes/                 # Classes management (empty scaffold)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   ├── permissions.py
│   └── admin.py
│
├── uploads/                 # File uploads & management (empty scaffold)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   └── admin.py
│
├── sharing/                 # File sharing system (empty scaffold)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   └── admin.py
│
├── friends/                 # Friends management (empty scaffold)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   └── admin.py
│
├── notifications/           # Notifications system (empty scaffold)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py
│   └── admin.py
│
├── core/                    # Shared utilities
│   ├── utils/
│   │   ├── responses.py     # Standard API responses
│   │   ├── validators.py    # Shared validators
│   │   └── code_generator.py # Code generation utility
│   ├── permissions.py       # Shared permissions (IsOwner, IsLecturer, IsStudent)
│   └── pagination.py        # Shared pagination classes
│
├── kibegi_api/              # Project settings
│   ├── settings.py
│   ├── urls.py
│   ├── middleware.py        # Request logging middleware
│   └── wsgi.py
│
├── media/                   # File uploads storage
├── logs/                    # Application logs
├── requirements.txt
├── .env
└── manage.py
```

## What I added:
- `authentication/` app with models, serializers, APIViews, urls, and standard response helpers
- `classes/`, `uploads/`, `sharing/`, `friends/`, `notifications/` app scaffolds (ready for implementation)
- `core/` utilities package with shared responses, permissions, pagination, and code generators
- `requirements.txt` listing dependencies
- `.env.example` with placeholders for secret and email credentials
- `README.md` (this file)
- Request logging middleware that logs all requests to `logs/kibegi_api.log`
- Media file handling configuration

## API Endpoints

### Authentication (Implemented)
- POST `/api/v1/auth/register/` - User registration (sends OTP)
- POST `/api/v1/auth/register/verify/` - Verify registration OTP (returns tokens)
- POST `/api/v1/auth/register/resend/` - Resend registration OTP (rate-limited: 5/25min)
- POST `/api/v1/auth/login/` - User login
- POST `/api/v1/auth/logout/` - User logout (blacklist token)
- POST `/api/v1/auth/token/refresh/` - Refresh access token
- POST `/api/v1/auth/password-reset/` - Request password reset (sends OTP)
- POST `/api/v1/auth/password-reset/verify/` - Verify password reset OTP (returns reset token)
- POST `/api/v1/auth/password-reset/resend/` - Resend password reset OTP
- POST `/api/v1/auth/password-reset-confirm/` - Confirm password reset with token
- POST `/api/v1/auth/change-password/` - Change password (authenticated)
- GET `/api/v1/auth/profile/` - Get user profile
- PUT/PATCH `/api/v1/auth/profile/` - Update user profile (username only)

### Other Apps (Empty - Ready for Implementation)
- `/api/v1/classes/` - Classes management endpoints
- `/api/v1/uploads/` - File upload endpoints
- `/api/v1/sharing/` - File sharing endpoints
- `/api/v1/friends/` - Friends management endpoints
- `/api/v1/notifications/` - Notifications endpoints

## Quick integration guide:
1. Install dependencies: `pip install -r requirements.txt` (use your virtualenv)
2. Add email credentials to your real `.env` file
3. Run migrations: `python manage.py makemigrations` then `python manage.py migrate`
4. Create superuser: `python manage.py createsuperuser`
5. Run dev server: `python manage.py runserver`

## Logging
- All requests are logged to `/logs/kibegi_api.log`
- View logs: `tail -f logs/kibegi_api.log`
- Sensitive fields (passwords, OTP codes) are automatically redacted

## Notes and next steps:
- Password reset (OTP/email) endpoints are implemented with email sending.
- Internationalization: activate `LocaleMiddleware` and add translations as needed.
- New app scaffolds are ready - implement models, serializers, and views as needed.
- Shared utilities in `core/` package for consistent responses and permissions across all apps.
