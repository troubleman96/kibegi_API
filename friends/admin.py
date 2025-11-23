from django.contrib import admin
from .models import Friendship


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    """
    Admin interface for Friendship model.
    
    Provides filtering, search, and read-only display.
    """
    list_display = [
        'id', 'user', 'friend', 'nickname',
        'status', 'created_at', 'accepted_at'
    ]
    list_filter = ['status', 'created_at', 'accepted_at']
    search_fields = [
        'user__email', 'user__full_name',
        'friend__email', 'friend__full_name',
        'nickname'
    ]
    readonly_fields = ['created_at', 'accepted_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Friendship', {
            'fields': ('user', 'friend', 'status')
        }),
        ('Customization', {
            'fields': ('nickname',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'accepted_at'),
            'classes': ('collapse',)
        }),
    )
