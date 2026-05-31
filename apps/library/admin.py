from django.contrib import admin

from .models import LibraryCategory, LibraryItem


@admin.register(LibraryCategory)
class LibraryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'slug')
    ordering = ('name',)


@admin.register(LibraryItem)
class LibraryItemAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'title', 'uploaded_by', 'file_type', 'category', 'status', 'is_featured', 'view_count', 'download_count', 'created_at')
    list_filter = ('status', 'file_type', 'category', 'is_featured', 'created_at')
    search_fields = ('item_code', 'title', 'description', 'subject', 'course_code', 'author_name', 'uploaded_by__email')
    ordering = ('-created_at',)
    readonly_fields = ('item_code', 'view_count', 'download_count', 'created_at', 'updated_at')
