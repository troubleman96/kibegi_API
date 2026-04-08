"""
Storage App Admin Configuration

This module configures the Django admin interface for storage models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import UserStorage, StorageUsageHistory


@admin.register(UserStorage)
class UserStorageAdmin(admin.ModelAdmin):
    """
    Enhanced UserStorage admin with:
    - Visual usage indicators
    - Progress bar for storage usage
    - Bulk actions for quota management
    """
    
    list_display = [
        'user_info',
        'quota_display',
        'usage_bar',
        'usage_percentage_display',
        'status_badge',
        'last_calculated',
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
    
    autocomplete_fields = ['user']
    ordering = ['-used_storage_bytes']
    
    actions = [
        'recalculate_storage',
        'increase_quota_10mb',
        'increase_quota_50mb',
        'reset_quota_to_default',
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Storage Quota', {
            'fields': ('total_quota_mb',),
            'description': 'Set the total storage quota for this user in megabytes.'
        }),
        ('Current Usage', {
            'fields': (
                'used_storage_mb',
                'free_storage_mb',
                'usage_percentage',
            )
        }),
        ('Status', {
            'fields': ('is_full',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_calculated'),
            'classes': ('collapse',)
        }),
    )
    
    def user_info(self, obj):
        """Display user with email and type"""
        color = '#10B981' if obj.user.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: #6B7280;">{}</small><br>'
            '<span style="color: {}; font-size: 10px;">{}</span>',
            obj.user.full_name,
            obj.user.email,
            color,
            obj.user.user_type.upper()
        )
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__full_name'
    
    def quota_display(self, obj):
        """Display quota information"""
        return format_html(
            '<strong>{:.2f}</strong> / {:.2f} MB<br>'
            '<small style="color: #6B7280;">Free: {:.2f} MB</small>',
            obj.used_storage_mb, float(obj.total_quota_mb), obj.free_storage_mb
        )
    quota_display.short_description = 'Storage'
    
    def usage_bar(self, obj):
        """Display usage as progress bar"""
        percentage = min(obj.usage_percentage, 100)
        
        # Color based on usage
        if percentage >= 90:
            color = '#EF4444'  # Red
        elif percentage >= 70:
            color = '#F59E0B'  # Amber
        else:
            color = '#10B981'  # Green
        
        return format_html(
            '<div style="width: 100px; background-color: #E5E7EB; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; height: 20px; background-color: {}; border-radius: 10px;"></div>'
            '</div>',
            percentage, color
        )
    usage_bar.short_description = 'Usage'
    
    def usage_percentage_display(self, obj):
        """Display usage percentage with color"""
        percentage = obj.usage_percentage
        if percentage >= 90:
            color = '#EF4444'
        elif percentage >= 70:
            color = '#F59E0B'
        else:
            color = '#10B981'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    usage_percentage_display.short_description = '%'
    
    def status_badge(self, obj):
        """Display storage status"""
        if obj.is_full:
            return format_html(
                '<span style="background-color: #EF4444; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 11px;">🚫 FULL</span>'
            )
        if obj.is_near_limit():
            return format_html(
                '<span style="background-color: #F59E0B; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 11px;">⚠️ Near Limit</span>'
            )
        return format_html(
            '<span style="background-color: #10B981; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 11px;">✓ OK</span>'
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('user')
    
    # Bulk Actions
    @admin.action(description='🔄 Recalculate storage for selected users')
    def recalculate_storage(self, request, queryset):
        from .services import StorageService
        count = 0
        for storage in queryset:
            StorageService.update_user_storage(storage.user, recalculate=True)
            count += 1
        self.message_user(request, f'Storage recalculated for {count} user(s).')
    
    @admin.action(description='➕ Increase quota by 10MB')
    def increase_quota_10mb(self, request, queryset):
        for storage in queryset:
            storage.total_quota_mb += 10
            storage.save()
        self.message_user(request, f'Quota increased by 10MB for {queryset.count()} user(s).')
    
    @admin.action(description='➕ Increase quota by 50MB')
    def increase_quota_50mb(self, request, queryset):
        for storage in queryset:
            storage.total_quota_mb += 50
            storage.save()
        self.message_user(request, f'Quota increased by 50MB for {queryset.count()} user(s).')
    
    @admin.action(description='↩️ Reset quota to default (50MB)')
    def reset_quota_to_default(self, request, queryset):
        queryset.update(total_quota_mb=50.0)
        self.message_user(request, f'Quota reset to 50MB for {queryset.count()} user(s).')


@admin.register(StorageUsageHistory)
class StorageUsageHistoryAdmin(admin.ModelAdmin):
    """
    Storage usage history admin for tracking changes over time.
    """
    
    list_display = [
        'user_info',
        'usage_display',
        'recorded_at',
    ]
    
    list_filter = [
        'recorded_at',
    ]
    
    search_fields = [
        'user_storage__user__email',
        'user_storage__user__full_name',
    ]
    
    readonly_fields = ['user_storage', 'used_storage_bytes', 'recorded_at']
    date_hierarchy = 'recorded_at'
    ordering = ['-recorded_at']
    
    def user_info(self, obj):
        """Display user info"""
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: #6B7280;">{}</small>',
            obj.user_storage.user.full_name,
            obj.user_storage.user.email
        )
    user_info.short_description = 'User'
    
    def usage_display(self, obj):
        """Display usage in MB"""
        mb = obj.used_storage_bytes / (1024 * 1024)
        return f"{mb:.2f} MB"
    usage_display.short_description = 'Used Storage'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_storage__user')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
