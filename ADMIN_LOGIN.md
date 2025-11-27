# Django Admin Login Guide

## How to Access Django Admin Panel

### 1. Access the Admin URL
Navigate to: **http://localhost:8000/admin/** (or your server URL)

### 2. Login Credentials

**Important:** Since your User model uses `email` as the username field, you must use your **email address** to log in, not a username.

**Your Superuser Account:**
- **Email:** `itslugenge96@icloud.com`
- **Password:** (the password you set when creating the superuser)

### 3. Login Steps

1. Go to: `http://localhost:8000/admin/`
2. Enter your **email address** in the "Email address" field: `itslugenge96@icloud.com`
3. Enter your **password** in the "Password" field
4. Click "Log in"

### 4. If You Forgot Your Password

If you can't remember your password, you can reset it using Django's shell:

```bash
# Activate virtual environment
source venv/bin/activate

# Open Django shell
python manage.py shell

# In the shell, run:
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email='itslugenge96@icloud.com')
user.set_password('your_new_password_here')
user.save()
print("Password changed successfully!")
exit()
```

### 5. Create a New Superuser (if needed)

If you need to create a new superuser:

```bash
# Activate virtual environment
source venv/bin/activate

# Create superuser
python manage.py createsuperuser
```

When prompted:
- **Email address:** Enter your email (e.g., `your-email@example.com`)
- **Full name:** Enter your full name
- **Password:** Enter a secure password
- **User type:** Choose `student` or `lecturer` (doesn't matter for admin access)

### 6. Verify Superuser Status

To check if your account is a superuser:

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email='itslugenge96@icloud.com')
print(f"Is Superuser: {user.is_superuser}")
print(f"Is Staff: {user.is_staff}")
print(f"Is Active: {user.is_active}")
```

All three should be `True` for admin access.

### 7. Common Issues

**Issue: "Please enter the correct email and password"**
- Make sure you're using your **email address**, not a username
- Check that your password is correct
- Verify the account is active: `user.is_active` should be `True`

**Issue: "You don't have permission to access the admin"**
- Check that `user.is_staff` is `True`
- Check that `user.is_superuser` is `True`

**Issue: Can't access admin URL**
- Make sure the server is running: `python manage.py runserver`
- Check that the URL is correct: `/admin/` (not `/admin`)
- Verify `path('admin/', admin.site.urls)` is in `kibegi_api/urls.py`

### 8. Admin Panel Features

Once logged in, you'll have access to:
- **Users** - Manage all user accounts
- **Classes** - View and manage classes
- **Uploads** - View uploaded files
- **Shared Files** - Manage file sharing
- **Friendships** - View friend relationships
- **Notifications** - View notifications
- **Storage** - View user storage records
- **Request Logs** - View API request logs

---

**Need Help?** If you're still having issues, check:
1. Server is running: `python manage.py runserver`
2. Database migrations are applied: `python manage.py migrate`
3. Your account exists and has superuser privileges

