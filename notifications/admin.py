from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for Notification model.
    
    Features:
    - List display with key fields
    - Filters by type, read status, and date
    - Search by user email and content
    - Readonly timestamps
    - Organized fieldsets
    """
    
    list_display = [
        'id',
        'user',
        'notification_type',
        'content_preview',
        'is_read',
        'created_at',
    ]
    
    list_filter = [
        'notification_type',
        'is_read',
        'created_at',
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'content',
        'related_object_id',
    ]
    
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'content', 'related_object_id')
        }),
        ('Status', {
            'fields': ('is_read', 'created_at')
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def content_preview(self, obj):
        """Show first 50 characters of content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    
    content_preview.short_description = 'Content'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related('user')
