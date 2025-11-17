# Kibegi Backend - Authentication App

This repository contains a scaffold for the `authentication` Django app implementing JWT authentication, custom user model, and localized messages (English/Swahili).

What I added:
- `authentication/` app with models, serializers, APIViews, urls, and standard response helpers
- `requirements.txt` listing dependencies
- `.env.example` with placeholders for secret and email credentials
- `README.md` (this file)

Quick integration guide:
1. Add `authentication` to `INSTALLED_APPS` in your Django project's `settings.py`.
2. Set `AUTH_USER_MODEL = 'authentication.User'` in `settings.py`.
3. Install dependencies: `pip install -r requirements.txt` (use your virtualenv)
4. Add REST framework and Simple JWT settings (example):

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

5. Wire URLs in your project `urls.py`:

```python
path('api/v1/auth/', include('authentication.urls')),
```

6. Add email credentials to your real `.env` file and implement the OTP/email sending logic in `PasswordResetRequestAPIView`.

Notes and next steps:
- Password reset (OTP/email) endpoints currently contain TODO placeholders for token generation and email sending; implement with `django.core.mail` and environment credentials.
- Internationalization: activate `LocaleMiddleware` and add translations as in your plan.
- Run migrations: `python manage.py makemigrations authentication` then `python manage.py migrate`.

If you want, I can now:
- Add a basic password-reset token model and email-sending implementation using the `.env` credentials you provide.
- Add tests for registration and login endpoints.
