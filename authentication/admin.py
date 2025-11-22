from django.contrib import admin
from .models import User, PasswordResetOTP


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'user_type', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_active', 'date_joined']
    search_fields = ['email', 'full_name']
    ordering = ['-date_joined']


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ['email', 'code', 'purpose', 'created_at', 'expires_at', 'is_used']
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['email', 'code']
    ordering = ['-created_at']
