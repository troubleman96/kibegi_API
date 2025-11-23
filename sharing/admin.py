from django.contrib import admin
from .models import SharedFile


@admin.register(SharedFile)
class SharedFileAdmin(admin.ModelAdmin):
    """
    Admin interface for SharedFile model.
    
    Read-only display showing share status and relationships.
    """
    list_display = [
        'id', 'upload', 'shared_by', 'shared_with',
        'status', 'shared_at', 'accepted_at', 'rejected_at'
    ]
    list_filter = ['status', 'shared_at', 'accepted_at']
    search_fields = [
        'upload__file_name', 'shared_by__email',
        'shared_with__email', 'message'
    ]
    readonly_fields = [
        'id', 'upload', 'shared_by', 'shared_with',
        'status', 'message', 'shared_at', 'accepted_at',
        'rejected_at'
    ]
    ordering = ['-shared_at']
    
    # Prevent adding/editing/deleting shares from admin
    def has_add_permission(self, request):
        """Shares can only be created through API"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Shares can only be modified through API"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Shares cannot be deleted (soft delete pattern)"""
        return False

