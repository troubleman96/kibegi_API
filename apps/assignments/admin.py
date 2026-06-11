from django.contrib import admin
from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'assignment_code', 'class_obj', 'created_by', 'due_date', 'is_active', 'created_at']
    list_filter = ['is_active', 'allow_late_submission', 'class_obj']
    search_fields = ['title', 'assignment_code', 'created_by__email']
    ordering = ['-created_at']
    readonly_fields = ['assignment_code', 'created_at', 'updated_at']


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'assignment', 'status', 'score', 'is_late', 'submitted_at']
    list_filter = ['status', 'is_late', 'assignment__class_obj']
    search_fields = ['student__email', 'assignment__title']
    ordering = ['-submitted_at']
    readonly_fields = ['created_at', 'updated_at']
