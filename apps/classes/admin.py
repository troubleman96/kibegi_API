"""
Classes App Admin Configuration

This module configures the Django admin interface for class-related models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import Class, Membership


# =============================================================================
# Membership Inline
# =============================================================================

class MembershipInline(admin.TabularInline):
    """Inline display of class memberships"""
    model = Membership
    extra = 0
    readonly_fields = ['joined_at']
    autocomplete_fields = ['user']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# =============================================================================
# Class Admin Configuration
# =============================================================================

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    """
    Enhanced Class admin with:
    - Visual badges for verification status
    - Member and upload statistics
    - Bulk actions
    - Advanced filtering
    """
    
    list_display = [
        'name', 
        'class_code',
        'verification_badge',
        'visibility_badge',
        'creator_info',
        'get_member_count',
        'get_upload_count',
        'get_total_storage',
        'created_at',
    ]
    
    list_filter = ['is_verified', 'is_public', 'created_at']
    search_fields = ['name', 'class_code', 'description', 'creator__email', 'creator__full_name']
    readonly_fields = ['id', 'class_code', 'created_at', 'updated_at']
    inlines = [MembershipInline]
    autocomplete_fields = ['creator']
    date_hierarchy = 'created_at'
    
    actions = ['verify_classes', 'unverify_classes', 'make_public', 'make_private']
    
    fieldsets = (
        ('Class Information', {
            'fields': ('id', 'name', 'description', 'class_code')
        }),
        ('Settings', {
            'fields': ('is_verified', 'is_public')
        }),
        ('Creator', {
            'fields': ('creator',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_badge(self, obj):
        """Display verification status as badge"""
        if obj.is_verified:
            return mark_safe(
                '<span style="background-color: #10B981; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 11px;">✓ Verified</span>'
            )
        return mark_safe(
            '<span style="background-color: #6B7280; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 11px;">Study Group</span>'
        )
    verification_badge.short_description = 'Status'
    verification_badge.admin_order_field = 'is_verified'
    
    def visibility_badge(self, obj):
        """Display visibility as badge"""
        if obj.is_public:
            return mark_safe('<span style="color: #3B82F6;">🌐 Public</span>')
        return mark_safe('<span style="color: #6B7280;">🔒 Private</span>')
    visibility_badge.short_description = 'Visibility'
    visibility_badge.admin_order_field = 'is_public'
    
    def creator_info(self, obj):
        """Display creator with type badge"""
        color = '#10B981' if obj.creator.user_type == 'lecturer' else '#3B82F6'
        return format_html(
            '{} <span style="color: {}; font-size: 10px;">({})</span>',
            obj.creator.full_name, color, obj.creator.user_type
        )
    creator_info.short_description = 'Creator'
    creator_info.admin_order_field = 'creator__full_name'
    
    def get_member_count(self, obj):
        """Get member count with link"""
        count = obj.members.count()
        return format_html('<strong>{}</strong> members', count)
    get_member_count.short_description = 'Members'
    
    def get_upload_count(self, obj):
        """Get upload count"""
        count = obj.uploads.filter(is_deleted=False).count()
        return f"{count} files"
    get_upload_count.short_description = 'Uploads'
    
    def get_total_storage(self, obj):
        """Get total storage used by class"""
        total = obj.uploads.filter(is_deleted=False).aggregate(
            total=Sum('file_size')
        )['total'] or 0
        mb = total / (1024 * 1024)
        return f"{mb:.2f} MB"
    get_total_storage.short_description = 'Storage'
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('creator').prefetch_related('members', 'uploads')
    
    # Bulk Actions
    @admin.action(description='✓ Verify selected classes')
    def verify_classes(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} class(es) verified.')
    
    @admin.action(description='✗ Remove verification from selected classes')
    def unverify_classes(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} class(es) unverified.')
    
    @admin.action(description='🌐 Make selected classes public')
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} class(es) made public.')
    
    @admin.action(description='🔒 Make selected classes private')
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} class(es) made private.')


# =============================================================================
# Membership Admin Configuration
# =============================================================================

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    """
    Enhanced Membership admin for managing class memberships.
    """
    
    list_display = ['user_info', 'class_info', 'role_badge', 'joined_at']
    list_filter = ['role', 'joined_at', 'class_obj__is_verified']
    search_fields = ['user__email', 'user__full_name', 'class_obj__name', 'class_obj__class_code']
    readonly_fields = ['joined_at']
    autocomplete_fields = ['user', 'class_obj']
    date_hierarchy = 'joined_at'
    
    actions = ['make_lecturers', 'make_students']
    
    def user_info(self, obj):
        """Display user with email"""
        return format_html(
            '{}<br><small style="color: #6B7280;">{}</small>',
            obj.user.full_name, obj.user.email
        )
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__full_name'
    
    def class_info(self, obj):
        """Display class with code"""
        return format_html(
            '{}<br><small style="color: #6B7280;">{}</small>',
            obj.class_obj.name, obj.class_obj.class_code
        )
    class_info.short_description = 'Class'
    class_info.admin_order_field = 'class_obj__name'
    
    def role_badge(self, obj):
        """Display role as colored badge"""
        colors = {
            'lecturer': '#10B981',
            'student': '#3B82F6',
        }
        color = colors.get(obj.role, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            color, obj.role.upper()
        )
    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'role'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'class_obj')
    
    @admin.action(description='🎓 Change role to Lecturer')
    def make_lecturers(self, request, queryset):
        updated = queryset.update(role='lecturer')
        self.message_user(request, f'{updated} membership(s) changed to lecturer.')
    
    @admin.action(description='📚 Change role to Student')
    def make_students(self, request, queryset):
        updated = queryset.update(role='student')
        self.message_user(request, f'{updated} membership(s) changed to student.')
