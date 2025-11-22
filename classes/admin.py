from django.contrib import admin
from .models import Class, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    readonly_fields = ['joined_at']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_code', 'creator', 'is_public', 'get_member_count', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['name', 'class_code', 'description', 'creator__email', 'creator__full_name']
    readonly_fields = ['id', 'class_code', 'created_at', 'updated_at']
    inlines = [MembershipInline]
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = 'Members'
    
    fieldsets = (
        ('Class Information', {
            'fields': ('id', 'name', 'description', 'class_code', 'is_public')
        }),
        ('Creator', {
            'fields': ('creator',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'class_obj', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__email', 'user__full_name', 'class_obj__name']
    readonly_fields = ['joined_at']