"""
Uploads App Admin Configuration

This module configures the Django admin interface for upload-related models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Upload


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    """
    Enhanced Upload admin with:
    - File type visualization
    - Size formatting
    - Status indicators
    - Bulk actions for deletion management
    """
    
    list_display = [
        'file_name',
        'file_code',
        'file_type_badge',
        'file_size_display',
        'uploader_info',
        'class_info',
        'status_badge',
        'created_at',
    ]
    
    list_filter = [
        'file_type',
        'is_deleted',
        'created_at',
        'uploader__user_type',
        'class_obj',
    ]
    
    search_fields = [
        'file_name',
        'file_code',
        'uploader__email',
        'uploader__full_name',
        'class_obj__name',
        'class_obj__class_code',
    ]
    
    readonly_fields = [
        'id',
        'file_code',
        'file_type',
        'file_size',
        'created_at',
        'updated_at',
        'deleted_at',
    ]
    
    autocomplete_fields = ['uploader', 'class_obj']
    date_hierarchy = 'created_at'
    
    actions = [
        'soft_delete_uploads',
        'restore_uploads',
        'permanent_delete_uploads',
    ]
    
    fieldsets = (
        ('File Information', {
            'fields': ('id', 'file', 'file_name', 'file_type', 'file_size', 'file_code')
        }),
        ('Relationships', {
            'fields': ('uploader', 'class_obj')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_type_badge(self, obj):
        """Display file type with icon and color"""
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
        colors = {
            'document': '#3B82F6',
            'image': '#10B981',
            'video': '#8B5CF6',
            'audio': '#F59E0B',
            'archive': '#6B7280',
            'spreadsheet': '#10B981',
            'presentation': '#EF4444',
            'other': '#6B7280',
        }
        icon = icons.get(obj.file_type, '📁')
        color = colors.get(obj.file_type, '#6B7280')
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.file_type.title()
        )
    file_type_badge.short_description = 'Type'
    file_type_badge.admin_order_field = 'file_type'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
    file_size_display.short_description = 'Size'
    file_size_display.admin_order_field = 'file_size'
    
    def uploader_info(self, obj):
        """Display uploader with type badge"""
        color = '#10B981' if obj.uploader.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '{}<br><small style="color: {};">{}</small>',
            obj.uploader.full_name, color, obj.uploader.user_type
        )
    uploader_info.short_description = 'Uploader'
    uploader_info.admin_order_field = 'uploader__full_name'
    
    def class_info(self, obj):
        """Display class with code"""
        if obj.class_obj:
            return format_html(
                '{}<br><small style="color: #6B7280;">{}</small>',
                obj.class_obj.name, obj.class_obj.class_code
            )
        return mark_safe('<span style="color: #6B7280;">—</span>')
    class_info.short_description = 'Class'
    class_info.admin_order_field = 'class_obj__name'
    
    def status_badge(self, obj):
        """Display deletion status"""
        if obj.is_deleted:
            days_ago = (timezone.now() - obj.deleted_at).days if obj.deleted_at else 0
            days_until_permanent = 21 - days_ago
            if days_until_permanent <= 0:
                return mark_safe('<span style="color: #EF4444;">🗑️ Ready for deletion</span>')
            return format_html(
                '<span style="color: #F59E0B;">🗑️ Deleted ({} days left)</span>',
                days_until_permanent
            )
        return mark_safe('<span style="color: #10B981;">✓ Active</span>')
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'is_deleted'
    
    def get_queryset(self, request):
        """Include all uploads (including deleted) and optimize queries"""
        return Upload.objects.all().select_related('uploader', 'class_obj')
    
    # Bulk Actions
    @admin.action(description='🗑️ Soft delete selected uploads')
    def soft_delete_uploads(self, request, queryset):
        count = 0
        for upload in queryset.filter(is_deleted=False):
            upload.soft_delete()
            count += 1
        self.message_user(request, f'{count} upload(s) soft deleted.')
    
    @admin.action(description='♻️ Restore selected uploads')
    def restore_uploads(self, request, queryset):
        count = 0
        for upload in queryset.filter(is_deleted=True):
            upload.restore()
            count += 1
        self.message_user(request, f'{count} upload(s) restored.')
    
    @admin.action(description='⚠️ Permanently delete selected uploads')
    def permanent_delete_uploads(self, request, queryset):
        # Only delete uploads that have been soft-deleted for 21+ days
        count = 0
        for upload in queryset.filter(is_deleted=True):
            if upload.is_permanently_deletable():
                upload.file.delete(save=False)  # Delete actual file
                upload.delete()
                count += 1
        self.message_user(
            request,
            f'{count} upload(s) permanently deleted. '
            f'(Only uploads deleted 21+ days ago can be permanently removed)'
        )
