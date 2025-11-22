from django.contrib import admin
from .models import Upload


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'file_code', 'uploader', 'class_obj', 'file_size', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'created_at', 'uploader__user_type']
    search_fields = ['file_name', 'file_code', 'uploader__email', 'uploader__full_name']
    readonly_fields = ['id', 'file_code', 'file_size', 'created_at', 'updated_at', 'deleted_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('File Information', {
            'fields': ('id', 'file', 'file_name', 'file_size', 'file_code')
        }),
        ('Relationships', {
            'fields': ('uploader', 'class_obj')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        """Include deleted uploads in admin"""
        return Upload.objects.all()

