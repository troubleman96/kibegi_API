import os
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _


def profile_image_path(instance, filename):
    """
    Generate upload path for user profile images.
    
    Format: profiles/{user_id}/{filename}
    """
    ext = filename.split('.')[-1]
    filename = f"profile.{ext}"
    return f'profiles/{instance.id}/{filename}'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, full_name, user_type='student', password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, user_type=user_type, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, full_name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('student', _('Student')),
        ('lecturer', _('Lecturer')),
    )

    email = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(_('full name'), max_length=255)
    user_type = models.CharField(_('user type'), max_length=10, choices=USER_TYPE_CHOICES, default='student')
    profile_image = models.ImageField(
        _('profile image'),
        upload_to=profile_image_path,
        null=True,
        blank=True,
        help_text="User profile picture. Upload an image file."
    )
    university = models.CharField(_('university'), max_length=255, blank=True, default='')
    phone_number = models.CharField(_('phone number'), max_length=20, blank=True, default='')
    phone_verified = models.BooleanField(_('phone verified'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    is_approved = models.BooleanField(
        _('approved'),
        default=True,
        help_text=_(
            'Lecturers must be approved by an admin before they can log in. '
            'Students are approved automatically.'
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email


class PasswordResetOTP(models.Model):
    """One-time password (OTP) or token used for password reset/verification.

    Fields:
        email: the email the OTP was issued for
        code: numeric OTP
        reset_token: uuid string returned after OTP verification to allow password reset
        created_at: timestamp for creation
        expires_at: timestamp for expiry
        is_used: whether the OTP/reset token has been used
    """
    email = models.EmailField(_('email address'))
    code = models.CharField(_('otp code'), max_length=32)
    purpose = models.CharField(_('purpose'), max_length=32, default='password_reset')
    reset_token = models.CharField(_('reset token'), max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('password reset otp')
        verbose_name_plural = _('password reset otps')

    def __str__(self):
        return f"OTP for {self.email} (used={self.is_used})"


class PhoneOTP(models.Model):
    """OTP for verifying a user's Tanzania phone number via SMS."""

    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 10

    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='phone_otps',
    )
    phone = models.CharField(max_length=20)
    otp = models.CharField(max_length=6)
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PhoneOTP {self.phone} verified={self.verified}"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.verified and not self.is_expired() and self.attempts < self.MAX_ATTEMPTS
