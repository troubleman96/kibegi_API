"""
Notifications App Admin Configuration

This module configures the Django admin interface for notification models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Enhanced Notification admin with:
    - Visual type indicators
    - Read status display
    - Bulk actions for management
    - User filtering
    """
    
    list_display = [
        'id',
        'user_info',
        'type_badge',
        'content_preview',
        'read_status',
        'related_object_id',
        'created_at',
    ]
    
    list_filter = [
        'notification_type',
        'is_read',
        'created_at',
        'user__user_type',
    ]
    
    search_fields = [
        'user__email',
        'user__full_name',
        'content',
        'related_object_id',
    ]
    
    readonly_fields = ['created_at']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    actions = [
        'mark_as_read',
        'mark_as_unread',
        'delete_old_notifications',
    ]
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'content', 'related_object_id')
        }),
        ('Status', {
            'fields': ('is_read', 'created_at')
        }),
    )
    
    def user_info(self, obj):
        """Display user with email"""
        color = '#10B981' if obj.user.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: {};">{}</small>',
            obj.user.full_name, color, obj.user.email
        )
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__full_name'
    
    def type_badge(self, obj):
        """Display notification type with icon and color"""
        icons = {
            'friend_request': '👥',
            'friend_accepted': '🤝',
            'file_shared': '📤',
            'share_accepted': '✅',
            'share_rejected': '❌',
            'class_invite': '🎓',
            'class_joined': '📚',
            'upload_complete': '📁',
            'system': '🔔',
        }
        colors = {
            'friend_request': '#3B82F6',
            'friend_accepted': '#10B981',
            'file_shared': '#8B5CF6',
            'share_accepted': '#10B981',
            'share_rejected': '#EF4444',
            'class_invite': '#F59E0B',
            'class_joined': '#10B981',
            'upload_complete': '#3B82F6',
            'system': '#6B7280',
        }
        icon = icons.get(obj.notification_type, '🔔')
        color = colors.get(obj.notification_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 10px; font-size: 10px;">{} {}</span>',
            color, icon, obj.notification_type.replace('_', ' ').title()
        )
    type_badge.short_description = 'Type'
    type_badge.admin_order_field = 'notification_type'
    
    def content_preview(self, obj):
        """Show first 60 characters of content"""
        preview = obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
        return format_html('<span style="color: #374151;">{}</span>', preview)
    content_preview.short_description = 'Content'
    
    def read_status(self, obj):
        """Display read status with icon"""
        if obj.is_read:
            return mark_safe('<span style="color: #10B981;">✓ Read</span>')
        return mark_safe('<span style="color: #F59E0B; font-weight: bold;">● Unread</span>')
    read_status.short_description = 'Status'
    read_status.admin_order_field = 'is_read'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    # Bulk Actions
    @admin.action(description='✓ Mark selected as read')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.')
    
    @admin.action(description='● Mark selected as unread')
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
    
    @admin.action(description='🗑️ Delete read notifications older than 30 days')
    def delete_old_notifications(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=30)
        count = queryset.filter(is_read=True, created_at__lt=cutoff).delete()[0]
        self.message_user(request, f'{count} old notification(s) deleted.')
