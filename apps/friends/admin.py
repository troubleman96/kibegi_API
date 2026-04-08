"""
Friends App Admin Configuration

This module configures the Django admin interface for friendship-related models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Friendship


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    """
    Enhanced Friendship admin with:
    - Status visualization
    - User info display
    - Bulk actions for managing requests
    - Time-based filtering
    """
    
    list_display = [
        'id',
        'sender_info',
        'direction_arrow',
        'recipient_info',
        'nickname',
        'status_badge',
        'created_at',
        'accepted_at',
    ]
    
    list_filter = [
        'status',
        'created_at',
        'accepted_at',
        'user__user_type',
        'friend__user_type',
    ]
    
    search_fields = [
        'user__email',
        'user__full_name',
        'friend__email',
        'friend__full_name',
        'nickname',
    ]
    
    readonly_fields = ['created_at', 'accepted_at']
    autocomplete_fields = ['user', 'friend']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    actions = [
        'accept_requests',
        'reject_requests',
        'delete_friendships',
    ]
    
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
    
    def sender_info(self, obj):
        """Display sender with type badge"""
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
    sender_info.short_description = 'Sender'
    sender_info.admin_order_field = 'user__full_name'
    
    def direction_arrow(self, obj):
        """Display arrow based on status"""
        if obj.status == 'pending':
            return mark_safe('<span style="font-size: 20px; color: #F59E0B;">→</span>')
        elif obj.status == 'accepted':
            return mark_safe('<span style="font-size: 20px; color: #10B981;">↔</span>')
        return mark_safe('<span style="font-size: 20px; color: #6B7280;">→</span>')
    direction_arrow.short_description = ''
    
    def recipient_info(self, obj):
        """Display recipient with type badge"""
        color = '#10B981' if obj.friend.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: #6B7280;">{}</small><br>'
            '<span style="color: {}; font-size: 10px;">{}</span>',
            obj.friend.full_name,
            obj.friend.email,
            color,
            obj.friend.user_type.upper()
        )
    recipient_info.short_description = 'Recipient'
    recipient_info.admin_order_field = 'friend__full_name'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#F59E0B',
            'accepted': '#10B981',
        }
        icons = {
            'pending': '⏳',
            'accepted': '✓',
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
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('user', 'friend')
    
    # Bulk Actions
    @admin.action(description='✓ Accept selected friend requests')
    def accept_requests(self, request, queryset):
        count = 0
        for friendship in queryset.filter(status='pending'):
            friendship.accept()
            count += 1
        self.message_user(request, f'{count} friend request(s) accepted.')
    
    @admin.action(description='✗ Reject selected friend requests')
    def reject_requests(self, request, queryset):
        count = queryset.filter(status='pending').delete()[0]
        self.message_user(request, f'{count} friend request(s) rejected/deleted.')
    
    @admin.action(description='🗑️ Delete selected friendships')
    def delete_friendships(self, request, queryset):
        count = queryset.delete()[0]
        self.message_user(request, f'{count} friendship(s) deleted.')
