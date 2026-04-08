"""
Core App Admin Configuration

This module configures the Django admin interface for core models
including request logging and system monitoring.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    """
    Enhanced RequestLog admin for monitoring API activity:
    - Color-coded status indicators
    - Response time visualization
    - Method badges
    - Advanced filtering and search
    """
    
    list_display = [
        'timestamp',
        'method_badge',
        'path_display',
        'user_info',
        'status_badge',
        'response_time_display',
        'ip_address',
    ]
    
    list_filter = [
        'method',
        'status_code',
        'timestamp',
    ]
    
    search_fields = [
        'path',
        'full_path',
        'user_email',
        'ip_address',
        'error_message',
    ]
    
    readonly_fields = [
        'timestamp',
        'method',
        'path',
        'full_path',
        'user',
        'user_email',
        'ip_address',
        'user_agent',
        'status_code',
        'response_time_ms',
        'request_body',
        'error_message',
    ]
    
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50
    
    fieldsets = (
        ('Request Info', {
            'fields': ('timestamp', 'method', 'path', 'full_path')
        }),
        ('User Info', {
            'fields': ('user', 'user_email', 'ip_address', 'user_agent')
        }),
        ('Response Info', {
            'fields': ('status_code', 'response_time_ms', 'error_message')
        }),
        ('Request Data', {
            'fields': ('request_body',),
            'classes': ('collapse',)
        }),
    )
    
    def method_badge(self, obj):
        """Display HTTP method with colored badge"""
        colors = {
            'GET': '#10B981',     # Green
            'POST': '#3B82F6',    # Blue
            'PUT': '#F59E0B',     # Amber
            'PATCH': '#8B5CF6',   # Purple
            'DELETE': '#EF4444',  # Red
            'OPTIONS': '#6B7280', # Gray
            'HEAD': '#6B7280',    # Gray
        }
        color = colors.get(obj.method, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.method
        )
    method_badge.short_description = 'Method'
    method_badge.admin_order_field = 'method'
    
    def path_display(self, obj):
        """Display truncated path"""
        path = obj.path
        if len(path) > 50:
            path = path[:50] + '...'
        return format_html('<code style="font-size: 12px;">{}</code>', path)
    path_display.short_description = 'Path'
    path_display.admin_order_field = 'path'
    
    def user_info(self, obj):
        """Display user email or anonymous"""
        if obj.user_email:
            return format_html(
                '<span style="color: #3B82F6;">{}</span>',
                obj.user_email
            )
        return format_html('<span style="color: #6B7280;">Anonymous</span>')
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user_email'
    
    def status_badge(self, obj):
        """Display status code with colored badge"""
        code = obj.status_code
        if 200 <= code < 300:
            color = '#10B981'  # Green - Success
            icon = '✓'
        elif 300 <= code < 400:
            color = '#3B82F6'  # Blue - Redirect
            icon = '↪'
        elif 400 <= code < 500:
            color = '#F59E0B'  # Amber - Client Error
            icon = '⚠'
        else:
            color = '#EF4444'  # Red - Server Error
            icon = '✗'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{} {}</span>',
            color, icon, code
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status_code'
    
    def response_time_display(self, obj):
        """Display response time with color coding"""
        time_ms = obj.response_time_ms
        if time_ms < 100:
            color = '#10B981'  # Green - Fast
        elif time_ms < 500:
            color = '#F59E0B'  # Amber - Medium
        else:
            color = '#EF4444'  # Red - Slow
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.0f}ms</span>',
            color, time_ms
        )
    response_time_display.short_description = 'Time'
    response_time_display.admin_order_field = 'response_time_ms'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        """Logs are system-generated only"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Logs are read-only"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow superusers to delete old logs"""
        return request.user.is_superuser
    
    # Custom actions
    actions = ['delete_old_logs']
    
    @admin.action(description='🗑️ Delete logs older than 30 days')
    def delete_old_logs(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=30)
        count = RequestLog.objects.filter(timestamp__lt=cutoff).delete()[0]
        self.message_user(request, f'{count} old log(s) deleted.')
