from django.contrib import admin
from .models import RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'method', 'path', 'user_email', 'status_code', 'response_time_ms', 'ip_address']
    list_filter = ['method', 'status_code', 'timestamp']
    search_fields = ['path', 'user_email', 'ip_address', 'full_path']
    readonly_fields = ['timestamp', 'method', 'path', 'full_path', 'user', 'user_email', 
                       'ip_address', 'user_agent', 'status_code', 'response_time_ms', 
                       'request_body', 'error_message']
    date_hierarchy = 'timestamp'
    
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
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
