"""
Sharing App Admin Configuration

This module configures the Django admin interface for file sharing models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import SharedFile


@admin.register(SharedFile)
class SharedFileAdmin(admin.ModelAdmin):
    """
    Enhanced SharedFile admin with:
    - Status visualization
    - File and user info display
    - Read-only protection with override option
    - Bulk actions for managing shares
    """
    
    list_display = [
        'id',
        'file_info',
        'sharer_info',
        'direction_arrow',
        'recipient_info',
        'status_badge',
        'message_preview',
        'shared_at',
    ]
    
    list_filter = [
        'status',
        'shared_at',
        'accepted_at',
        'rejected_at',
        'shared_by__user_type',
        'shared_with__user_type',
    ]
    
    search_fields = [
        'upload__file_name',
        'upload__file_code',
        'shared_by__email',
        'shared_by__full_name',
        'shared_with__email',
        'shared_with__full_name',
        'message',
    ]
    
    readonly_fields = [
        'id',
        'upload',
        'shared_by',
        'shared_with',
        'message',
        'shared_at',
        'accepted_at',
        'rejected_at',
    ]
    
    ordering = ['-shared_at']
    date_hierarchy = 'shared_at'
    
    actions = [
        'accept_shares',
        'reject_shares',
        'reset_to_pending',
    ]
    
    fieldsets = (
        ('Share Details', {
            'fields': ('id', 'upload', 'shared_by', 'shared_with')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Message', {
            'fields': ('message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('shared_at', 'accepted_at', 'rejected_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_info(self, obj):
        """Display file with type icon"""
        icons = {
            'document': '📄',
            'image': '🖼️',
            'video': '🎬',
            'audio': '🎵',
            'archive': '📦',
            'spreadsheet': '📊',
            'presentation': '📽️',
            'other': '📁',
        }
        icon = icons.get(obj.upload.file_type, '📁')
        return format_html(
            '{} <strong>{}</strong><br>'
            '<small style="color: #6B7280;">{}</small>',
            icon, obj.upload.file_name[:30] + '...' if len(obj.upload.file_name) > 30 else obj.upload.file_name,
            obj.upload.file_code
        )
    file_info.short_description = 'File'
    file_info.admin_order_field = 'upload__file_name'
    
    def sharer_info(self, obj):
        """Display sharer with type"""
        color = '#10B981' if obj.shared_by.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: {};">{}</small>',
            obj.shared_by.full_name, color, obj.shared_by.user_type
        )
    sharer_info.short_description = 'Shared By'
    sharer_info.admin_order_field = 'shared_by__full_name'
    
    def direction_arrow(self, obj):
        """Display arrow based on status"""
        arrows = {
            'pending': '<span style="font-size: 20px; color: #F59E0B;">→</span>',
            'accepted': '<span style="font-size: 20px; color: #10B981;">✓→</span>',
            'rejected': '<span style="font-size: 20px; color: #EF4444;">✗→</span>',
        }
        return format_html(arrows.get(obj.status, '→'))
    direction_arrow.short_description = ''
    
    def recipient_info(self, obj):
        """Display recipient with type"""
        color = '#10B981' if obj.shared_with.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: {};">{}</small>',
            obj.shared_with.full_name, color, obj.shared_with.user_type
        )
    recipient_info.short_description = 'Shared With'
    recipient_info.admin_order_field = 'shared_with__full_name'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#F59E0B',
            'accepted': '#10B981',
            'rejected': '#EF4444',
        }
        icons = {
            'pending': '⏳',
            'accepted': '✓',
            'rejected': '✗',
        }
        color = colors.get(obj.status, '#6B7280')
        icon = icons.get(obj.status, '')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 10px; font-size: 11px;">{} {}</span>',
            color, icon, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def message_preview(self, obj):
        """Show truncated message"""
        if obj.message:
            preview = obj.message[:40] + '...' if len(obj.message) > 40 else obj.message
            return format_html('<span style="color: #6B7280;">{}</span>', preview)
        return format_html('<span style="color: #D1D5DB;">—</span>')
    message_preview.short_description = 'Message'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'upload', 'shared_by', 'shared_with', 'upload__uploader'
        )
    
    # Override permissions to allow admin management
    def has_add_permission(self, request):
        """Allow superusers to create shares"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Allow superusers to modify shares"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Allow superusers to delete shares"""
        return request.user.is_superuser
    
    # Bulk Actions
    @admin.action(description='✓ Accept selected shares')
    def accept_shares(self, request, queryset):
        count = 0
        for share in queryset.filter(status='pending'):
            share.accept()
            count += 1
        self.message_user(request, f'{count} share(s) accepted.')
    
    @admin.action(description='✗ Reject selected shares')
    def reject_shares(self, request, queryset):
        count = 0
        for share in queryset.filter(status='pending'):
            share.reject()
            count += 1
        self.message_user(request, f'{count} share(s) rejected.')
    
    @admin.action(description='⏳ Reset selected shares to pending')
    def reset_to_pending(self, request, queryset):
        count = queryset.update(status='pending', accepted_at=None, rejected_at=None)
        self.message_user(request, f'{count} share(s) reset to pending.')
