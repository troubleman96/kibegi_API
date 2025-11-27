"""
Authentication App Admin Configuration

This module configures the Django admin interface for authentication models
and customizes the admin site appearance.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum
from .models import User, PasswordResetOTP


# =============================================================================
# Customize Admin Site Header and Title
# =============================================================================

admin.site.site_header = "📚 Kibegi Administration"
admin.site.site_title = "Kibegi Admin"
admin.site.index_title = "Welcome to Kibegi Control Panel"


# =============================================================================
# User Admin Configuration
# =============================================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Enhanced User admin with:
    - Custom list display with statistics
    - Bulk actions (activate, deactivate, change type)
    - Advanced filtering
    - Inline statistics
    """
    
    # List display configuration
    list_display = [
        'profile_image_thumbnail',
        'email', 
        'full_name', 
        'user_type_badge',
        'is_active_badge',
        'is_staff',
        'get_classes_count',
        'get_uploads_count',
        'get_friends_count',
        'date_joined',
    ]
    
    list_filter = [
        'user_type', 
        'is_active', 
        'is_staff',
        'is_superuser',
        'date_joined',
    ]
    
    search_fields = ['email', 'full_name']
    ordering = ['-date_joined']
    
    # Fieldsets for detail view
    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'user_type', 'profile_image', 'profile_image_preview')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'user_type', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login', 'profile_image_preview']
    filter_horizontal = ('groups', 'user_permissions')
    
    def profile_image_thumbnail(self, obj):
        """Display profile image thumbnail in list view"""
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;" />',
                obj.profile_image.url
            )
        return format_html(
            '<div style="width: 40px; height: 40px; border-radius: 50%; background-color: #E5E7EB; '
            'display: flex; align-items: center; justify-content: center; color: #6B7280; font-size: 18px;">👤</div>'
        )
    profile_image_thumbnail.short_description = 'Photo'
    
    def profile_image_preview(self, obj):
        """Display profile image preview in detail view"""
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px; border: 2px solid #E5E7EB;" />',
                obj.profile_image.url
            )
        return format_html('<span style="color: #6B7280;">No profile image</span>')
    profile_image_preview.short_description = 'Profile Image Preview'
    
    # Actions
    actions = [
        'activate_users',
        'deactivate_users',
        'make_students',
        'make_lecturers',
    ]
    
    def user_type_badge(self, obj):
        """Display user type as a colored badge"""
        colors = {
            'student': '#3B82F6',  # Blue
            'lecturer': '#10B981',  # Green
        }
        color = colors.get(obj.user_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.user_type.upper()
        )
    user_type_badge.short_description = 'Type'
    user_type_badge.admin_order_field = 'user_type'
    
    def is_active_badge(self, obj):
        """Display active status as a colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="color: #10B981;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: #EF4444;">✗ Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    is_active_badge.admin_order_field = 'is_active'
    
    def get_classes_count(self, obj):
        """Get number of classes user is member of"""
        return obj.joined_classes.count()
    get_classes_count.short_description = 'Classes'
    
    def get_uploads_count(self, obj):
        """Get number of uploads by user"""
        return obj.uploads.filter(is_deleted=False).count()
    get_uploads_count.short_description = 'Uploads'
    
    def get_friends_count(self, obj):
        """Get number of accepted friendships"""
        from friends.models import Friendship
        from django.db.models import Q
        return Friendship.objects.filter(
            Q(user=obj) | Q(friend=obj),
            status='accepted'
        ).count()
    get_friends_count.short_description = 'Friends'
    
    def get_queryset(self, request):
        """Optimize queries with annotations"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('joined_classes', 'uploads')
    
    # Bulk Actions
    @admin.action(description='✓ Activate selected users')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) activated.')
    
    @admin.action(description='✗ Deactivate selected users')
    def deactivate_users(self, request, queryset):
        updated = queryset.filter(is_superuser=False).update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated.')
    
    @admin.action(description='📚 Change to Student')
    def make_students(self, request, queryset):
        updated = queryset.update(user_type='student')
        self.message_user(request, f'{updated} user(s) changed to student.')
    
    @admin.action(description='🎓 Change to Lecturer')
    def make_lecturers(self, request, queryset):
        updated = queryset.update(user_type='lecturer')
        self.message_user(request, f'{updated} user(s) changed to lecturer.')


# =============================================================================
# Password Reset OTP Admin Configuration
# =============================================================================

@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    """
    Enhanced OTP admin with:
    - Status indicators
    - Expiry checking
    - Bulk invalidation
    """
    
    list_display = [
        'email', 
        'code', 
        'purpose_badge',
        'status_badge',
        'created_at', 
        'expires_at',
    ]
    
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['email', 'code']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    readonly_fields = ['email', 'code', 'purpose', 'reset_token', 'created_at', 'expires_at']
    
    actions = ['invalidate_otps']
    
    def purpose_badge(self, obj):
        """Display purpose as badge"""
        colors = {
            'password_reset': '#F59E0B',  # Amber
            'registration': '#3B82F6',    # Blue
        }
        color = colors.get(obj.purpose, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 10px;">{}</span>',
            color, obj.purpose.replace('_', ' ').title()
        )
    purpose_badge.short_description = 'Purpose'
    
    def status_badge(self, obj):
        """Display status based on usage and expiry"""
        if obj.is_used:
            return format_html('<span style="color: #6B7280;">● Used</span>')
        if obj.expires_at < timezone.now():
            return format_html('<span style="color: #EF4444;">● Expired</span>')
        return format_html('<span style="color: #10B981;">● Active</span>')
    status_badge.short_description = 'Status'
    
    @admin.action(description='🚫 Invalidate selected OTPs')
    def invalidate_otps(self, request, queryset):
        updated = queryset.update(is_used=True)
        self.message_user(request, f'{updated} OTP(s) invalidated.')
    
    def has_add_permission(self, request):
        """OTPs are system-generated only"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow only marking as used"""
        return True
