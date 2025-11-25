"""
Storage App Admin Configuration

This module configures the Django admin interface for storage models.
"""
from django.contrib import admin
from .models import UserStorage, StorageUsageHistory


@admin.register(UserStorage)
class UserStorageAdmin(admin.ModelAdmin):
    """
    Admin interface for UserStorage model.
    
    Displays storage information in a user-friendly format
    with search and filter capabilities.
    """
    
    list_display = [
        'user',
        'total_quota_mb',
        'used_storage_mb',
        'free_storage_mb',
        'usage_percentage',
        'is_full',
        'last_calculated',
        'updated_at',
    ]
    
    list_filter = [
        'total_quota_mb',
        'last_calculated',
    ]
    
    search_fields = [
        'user__email',
        'user__full_name',
    ]
    
    readonly_fields = [
        'used_storage_bytes',
        'used_storage_mb',
        'free_storage_mb',
        'free_storage_bytes',
        'usage_percentage',
        'is_full',
        'created_at',
        'updated_at',
        'last_calculated',
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Storage Quota', {
            'fields': ('total_quota_mb',)
        }),
        ('Current Usage', {
            'fields': (
                'used_storage_bytes',
                'used_storage_mb',
                'free_storage_mb',
                'free_storage_bytes',
                'usage_percentage',
            )
        }),
        ('Status', {
            'fields': ('is_full',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_calculated')
        }),
    )


@admin.register(StorageUsageHistory)
class StorageUsageHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for StorageUsageHistory model.
    
    Displays historical storage usage data.
    """
    
    list_display = [
        'user_storage',
        'get_used_storage_mb',
        'used_storage_bytes',
        'recorded_at',
    ]
    
    def get_used_storage_mb(self, obj):
        """Display used storage in megabytes"""
        return f"{round(obj.used_storage_bytes / (1024 * 1024), 2)} MB"
    get_used_storage_mb.short_description = 'Used Storage (MB)'
    
    list_filter = [
        'recorded_at',
    ]
    
    search_fields = [
        'user_storage__user__email',
        'user_storage__user__full_name',
    ]
    
    readonly_fields = [
        'recorded_at',
    ]
    
    date_hierarchy = 'recorded_at'
